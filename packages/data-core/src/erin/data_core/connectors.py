"""
ERIN Data Core - Acquisition Connectors
Modular connectors for REST APIs, RSS/Atom feeds, sitemaps, documents (PDF/CSV/XLSX), and regulatory publications.
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
import mimetypes
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, List, Dict, AsyncIterator, Callable, Awaitable, Union
from urllib.parse import urljoin, urlparse

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from erin.data_core.source_registry import (
    Source,
    SourceRegistry,
    SourceConfiguration,
    AccessMethod,
    AuthenticationType
)

logger = structlog.get_logger(__name__)


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_id: str = ""
    records_count: int = 0
    watermark: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorConfig:
    """Configuration for a connector."""
    source: Source
    watermark: Optional[str] = None
    incremental: bool = True
    batch_size: int = 1000
    max_concurrent_requests: int = 5
    request_timeout: int = 30
    custom_headers: Dict[str, str] = field(default_factory=dict)


class BaseConnector(ABC):
    """Base class for all data connectors."""
    
    def __init__(self, config: ConnectorConfig, registry: SourceRegistry):
        self.config = config
        self.registry = registry
        self.source = config.source
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._session: Optional[aiohttp.ClientSession] = None
        self._watermark = config.watermark
    
    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Unique identifier for this connector type."""
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        headers = {'User-Agent': 'ERIN-Connector/1.0'}
        headers.update(self.config.custom_headers)
        
        # Add authentication headers
        auth_headers = self._build_auth_headers()
        headers.update(auth_headers)
        
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _build_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers based on source config."""
        headers = {}
        auth = self.source.authentication
        config = self.source.config
        
        if auth == AuthenticationType.API_KEY:
            # API key can be in header, query param, or custom
            api_key = config.custom.get('api_key') or config.headers.get('Authorization')
            if api_key:
                # Default to Authorization header, but can be customized
                key_header = config.custom.get('api_key_header', 'Authorization')
                key_prefix = config.custom.get('api_key_prefix', 'Bearer')
                headers[key_header] = f"{key_prefix} {api_key}"
        elif auth == AuthenticationType.BEARER_TOKEN:
            token = config.headers.get('Authorization') or config.custom.get('bearer_token')
            if token:
                headers['Authorization'] = f"Bearer {token}"
        elif auth == AuthenticationType.BASIC_AUTH:
            username = config.custom.get('username')
            password = config.custom.get('password')
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers['Authorization'] = f"Basic {credentials}"
        elif auth == AuthenticationType.CUSTOM_HEADER:
            for k, v in config.headers.items():
                headers[k] = v
        
        return headers
    
    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _fetch_with_retry(self, url: str, method: str = "GET", **kwargs) -> aiohttp.ClientResponse:
        """Fetch with exponential backoff retry."""
        if not self._session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        async with self._semaphore:
            return await self._session.request(method, url, **kwargs)
    
    async def fetch(self) -> FetchResult:
        """Main fetch method - implements incremental sync, deduplication, checkpointing."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate source is ready
            if self.source.operational_status not in ["active", "degraded"]:
                return FetchResult(
                    success=False,
                    error=f"Source not operational: {self.source.operational_status}",
                    source_id=self.source.source_id
                )
            
            # Perform the actual fetch
            result = await self._fetch_data()
            
            # Update watermark if provided
            if result.watermark:
                self._watermark = result.watermark
            
            # Record success
            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            await self.registry.record_fetch_result(
                self.source.source_id,
                True,
                latency_ms
            )
            
            return FetchResult(
                success=True,
                data=result.data,
                latency_ms=latency_ms,
                source_id=self.source.source_id,
                records_count=result.records_count,
                watermark=result.watermark,
                metadata=result.metadata
            )
        
        except Exception as e:
            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            await self.registry.record_fetch_result(
                self.source.source_id,
                False,
                latency_ms,
                str(e)
            )
            
            return FetchResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
                source_id=self.source.source_id
            )
    
    @abstractmethod
    async def _fetch_data(self) -> FetchResult:
        """Implement the actual data fetching logic."""
        pass
    
    def _compute_record_hash(self, record: Dict[str, Any]) -> str:
        """Compute hash for deduplication."""
        # Sort keys for consistent hashing
        record_str = json.dumps(record, sort_keys=True, default=str)
        return hashlib.sha256(record_str.encode()).hexdigest()[:16]
    
    def _deduplicate_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate records based on content hash."""
        seen = set()
        unique = []
        for record in records:
            record_hash = self._compute_record_hash(record)
            if record_hash not in seen:
                seen.add(record_hash)
                unique.append(record)
        return unique


class RestApiConnector(BaseConnector):
    """Connector for REST APIs with pagination support."""
    
    @property
    def connector_type(self) -> str:
        return "rest_api"
    
    async def _fetch_data(self) -> FetchResult:
        config = self.source.config
        all_records = []
        watermark = None
        
        # Determine which endpoint to fetch
        endpoint_name = config.custom.get('endpoint', 'default')
        endpoint_path = config.endpoints.get(endpoint_name, '')
        base_url = config.base_url.rstrip('/')
        url = f"{base_url}{endpoint_path}"
        
        # Build query parameters
        params = dict(config.query_params)
        
        # Add watermark for incremental fetch
        if self.config.incremental and self._watermark:
            watermark_param = config.custom.get('watermark_param', 'since')
            params[watermark_param] = self._watermark
        
        # Handle pagination
        pagination_config = config.pagination
        page_param = pagination_config.get('page_param', 'page')
        limit_param = pagination_config.get('limit_param', 'limit')
        max_pages = pagination_config.get('max_pages', 100)
        page = 1
        
        while page <= max_pages:
            if page_param:
                params[page_param] = page
            if limit_param:
                params[limit_param] = pagination_config.get('page_size', self.config.batch_size)
            
            try:
                response = await self._fetch_with_retry(url, params=params)
                
                if response.status != 200:
                    error_text = await response.text()
                    return FetchResult(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}",
                        source_id=self.source.source_id
                    )
                
                data = await response.json()
                
                # Extract records from response
                records = self._extract_records(data)
                if not records:
                    break
                
                all_records.extend(records)
                
                # Check for next page
                if not self._has_next_page(data, response):
                    break
                
                page += 1
                
                # Small delay between pages
                await asyncio.sleep(0.1)
                
            except asyncio.TimeoutError:
                return FetchResult(
                    success=False,
                    error="Request timeout",
                    source_id=self.source.source_id
                )
            except Exception as e:
                return FetchResult(
                    success=False,
                    error=str(e),
                    source_id=self.source.source_id
                )
        
        # Deduplicate
        all_records = self._deduplicate_records(all_records)
        
        # Determine new watermark
        new_watermark = self._extract_watermark(all_records, data if 'data' in locals() else {})
        
        return FetchResult(
            success=True,
            data=all_records,
            records_count=len(all_records),
            watermark=new_watermark,
            source_id=self.source.source_id,
            metadata={"endpoint": endpoint_name, "pages_fetched": page - 1}
        )
    
    def _extract_records(self, data: Any) -> List[Dict[str, Any]]:
        """Extract records from API response."""
        # Default: assume data is a list or has 'data', 'results', 'items' key
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ['data', 'results', 'items', 'records', 'observations']:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Single object response
            return [data]
        return []
    
    def _has_next_page(self, data: Any, response: aiohttp.ClientResponse) -> bool:
        """Check if there's a next page."""
        pagination_config = self.source.config.pagination
        
        # Check Link header
        link_header = response.headers.get('Link', '')
        if 'rel="next"' in link_header:
            return True
        
        # Check JSON response for pagination info
        if isinstance(data, dict):
            for key in ['has_more', 'has_next', 'next_page', 'pagination']:
                if key in data:
                    val = data[key]
                    if isinstance(val, bool):
                        return val
                    if isinstance(val, dict) and val.get('next'):
                        return True
        
        return False
    
    def _extract_watermark(self, records: List[Dict[str, Any]], response_data: Any) -> Optional[str]:
        """Extract watermark for next incremental fetch."""
        watermark_config = self.source.config.custom.get('watermark_field')
        if not watermark_config or not records:
            return None
        
        # Try to get the latest value of the watermark field
        watermark_values = []
        for record in records:
            # Handle nested fields with dot notation
            value = record
            for key in watermark_config.split('.'):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    value = None
                    break
            if value is not None:
                watermark_values.append(str(value))
        
        if watermark_values:
            # Return the maximum (latest) value
            return max(watermark_values)
        return None


class RssFeedConnector(BaseConnector):
    """Connector for RSS and Atom feeds."""
    
    @property
    def connector_type(self) -> str:
        return "rss_feed"
    
    async def _fetch_data(self) -> FetchResult:
        config = self.source.config
        endpoint_path = config.endpoints.get('feed', '/rss.xml')
        base_url = config.base_url.rstrip('/')
        url = f"{base_url}{endpoint_path}"
        
        try:
            response = await self._fetch_with_retry(url)
            
            if response.status != 200:
                return FetchResult(
                    success=False,
                    error=f"HTTP {response.status}",
                    source_id=self.source.source_id
                )
            
            content = await response.text()
            
            # Parse feed
            import feedparser
            feed = feedparser.parse(content)
            
            records = []
            for entry in feed.entries:
                record = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'description': entry.get('description', '') or entry.get('summary', ''),
                    'published': entry.get('published', '') or entry.get('updated', ''),
                    'author': entry.get('author', ''),
                    'tags': [tag.term for tag in entry.get('tags', [])],
                    'source_feed': url,
                    'fetched_at': datetime.now(timezone.utc).isoformat()
                }
                
                # Add any additional fields
                for key, value in entry.items():
                    if key not in record and not key.startswith('_'):
                        record[key] = value
                
                records.append(record)
            
            # Deduplicate
            records = self._deduplicate_records(records)
            
            # Watermark: latest publication date
            watermark = None
            if records and self.config.incremental:
                dates = []
                for r in records:
                    for field in ['published', 'updated', 'pubDate', 'pubdate']:
                        if r.get(field):
                            dates.append(r[field])
                            break
                if dates:
                    watermark = max(dates)
            
            return FetchResult(
                success=True,
                data=records,
                records_count=len(records),
                watermark=watermark,
                source_id=self.source.source_id,
                metadata={"feed_title": feed.feed.get('title', ''), "feed_url": url}
            )
        
        except Exception as e:
            return FetchResult(
                success=False,
                error=str(e),
                source_id=self.source.source_id
            )


class SitemapConnector(BaseConnector):
    """Connector for XML sitemaps."""
    
    @property
    def connector_type(self) -> str:
        return "sitemap"
    
    async def _fetch_data(self) -> FetchResult:
        config = self.source.config
        endpoint_path = config.endpoints.get('sitemap', '/sitemap.xml')
        base_url = config.base_url.rstrip('/')
        url = f"{base_url}{endpoint_path}"
        
        try:
            response = await self._fetch_with_retry(url)
            
            if response.status != 200:
                return FetchResult(
                    success=False,
                    error=f"HTTP {response.status}",
                    source_id=self.source.source_id
                )
            
            content = await response.text()
            
            # Parse sitemap
            from xml.etree import ElementTree as ET
            root = ET.fromstring(content)
            namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            records = []
            
            # Handle sitemap index (references to other sitemaps)
            for sitemap_elem in root.findall('.//sm:sitemap', namespace):
                loc = sitemap_elem.find('sm:loc', namespace)
                if loc is not None and loc.text:
                    # Recursively fetch sub-sitemap
                    sub_connector = SitemapConnector(
                        ConnectorConfig(
                            source=self.source,
                            watermark=self._watermark,
                            incremental=self.config.incremental,
                            batch_size=self.config.batch_size
                        ),
                        self.registry
                    )
                    async with sub_connector:
                        sub_result = await sub_connector.fetch()
                        if sub_result.success:
                            records.extend(sub_result.data or [])
            
            # Handle regular URLs
            for url_elem in root.findall('.//sm:url', namespace):
                loc = url_elem.find('sm:loc', namespace)
                lastmod = url_elem.find('sm:lastmod', namespace)
                changefreq = url_elem.find('sm:changefreq', namespace)
                priority = url_elem.find('sm:priority', namespace)
                
                if loc is not None and loc.text:
                    record = {
                        'url': loc.text,
                        'lastmod': lastmod.text if lastmod is not None else None,
                        'changefreq': changefreq.text if changefreq is not None else None,
                        'priority': priority.text if priority is not None else None,
                        'source_sitemap': url,
                        'fetched_at': datetime.now(timezone.utc).isoformat()
                    }
                    records.append(record)
            
            # Deduplicate
            records = self._deduplicate_records(records)
            
            # Watermark: latest lastmod
            watermark = None
            if records and self.config.incremental:
                dates = [r['lastmod'] for r in records if r.get('lastmod')]
                if dates:
                    watermark = max(dates)
            
            return FetchResult(
                success=True,
                data=records,
                records_count=len(records),
                watermark=watermark,
                source_id=self.source.source_id,
                metadata={"sitemap_url": url}
            )
        
        except Exception as e:
            return FetchResult(
                success=False,
                error=str(e),
                source_id=self.source.source_id
            )


class DocumentConnector(BaseConnector):
    """Connector for document files (PDF, CSV, XLSX, JSON)."""
    
    @property
    def connector_type(self) -> str:
        return "document"
    
    async def _fetch_data(self) -> FetchResult:
        config = self.source.config
        
        # Determine document URLs to fetch
        doc_urls = []
        
        # If endpoints specify direct document URLs
        for name, path in config.endpoints.items():
            if any(path.endswith(ext) for ext in ['.pdf', '.csv', '.xlsx', '.xls', '.json', '.xml']):
                base_url = config.base_url.rstrip('/')
                doc_urls.append(f"{base_url}{path}")
        
        # If custom document_urls provided
        if config.custom.get('document_urls'):
            doc_urls.extend(config.custom['document_urls'])
        
        if not doc_urls:
            return FetchResult(
                success=False,
                error="No document URLs configured",
                source_id=self.source.source_id
            )
        
        all_records = []
        
        for doc_url in doc_urls:
            try:
                records = await self._fetch_document(doc_url)
                all_records.extend(records)
            except Exception as e:
                logger.warning("Failed to fetch document", url=doc_url, error=str(e))
        
        # Deduplicate
        all_records = self._deduplicate_records(all_records)
        
        return FetchResult(
            success=True,
            data=all_records,
            records_count=len(all_records),
            source_id=self.source.source_id,
            metadata={"documents_fetched": len(doc_urls)}
        )
    
    async def _fetch_document(self, url: str) -> List[Dict[str, Any]]:
        """Fetch and parse a single document."""
        response = await self._fetch_with_retry(url)
        
        if response.status != 200:
            raise Exception(f"HTTP {response.status}")
        
        content = await response.read()
        content_type = response.headers.get('Content-Type', '')
        
        # Determine file type from URL or content-type
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        
        if ext == '.csv' or 'csv' in content_type:
            return self._parse_csv(content)
        elif ext in ['.xlsx', '.xls'] or 'spreadsheet' in content_type or 'excel' in content_type:
            return self._parse_excel(content)
        elif ext == '.json' or 'json' in content_type:
            return self._parse_json(content)
        elif ext == '.pdf' or 'pdf' in content_type:
            return await self._parse_pdf(content, url)
        elif ext == '.xml' or 'xml' in content_type:
            return self._parse_xml(content)
        else:
            # Try to guess
            if content.startswith(b'%PDF'):
                return await self._parse_pdf(content, url)
            elif content.startswith(b'PK\x03\x04'):  # ZIP/XLSX signature
                return self._parse_excel(content)
            else:
                raise Exception(f"Unsupported document type: {ext} ({content_type})")
    
    def _parse_csv(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse CSV content."""
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('latin-1')
        
        reader = csv.DictReader(io.StringIO(text))
        records = []
        for row in reader:
            row['_source_format'] = 'csv'
            records.append(row)
        return records
    
    def _parse_excel(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse Excel content."""
        try:
            import openpyxl
        except ImportError:
            raise Exception("openpyxl not installed")
        
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        records = []
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            headers = None
            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx == 0:
                    headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(row)]
                    continue
                
                if headers and any(c is not None for c in row):
                    record = dict(zip(headers, row))
                    record['_sheet'] = sheet_name
                    record['_source_format'] = 'excel'
                    records.append(record)
        
        return records
    
    def _parse_json(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse JSON content."""
        try:
            data = json.loads(content.decode('utf-8'))
        except UnicodeDecodeError:
            data = json.loads(content.decode('latin-1'))
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item['_source_format'] = 'json'
            return data
        elif isinstance(data, dict):
            data['_source_format'] = 'json'
            return [data]
        return []
    
    def _parse_xml(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse XML content."""
        from xml.etree import ElementTree as ET
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return []
        
        records = []
        
        # Convert XML to records - assume repeating elements are records
        for child in root:
            record = self._xml_element_to_dict(child)
            record['_source_format'] = 'xml'
            records.append(record)
        
        return records
    
    def _xml_element_to_dict(self, element) -> Dict[str, Any]:
        """Convert XML element to dictionary."""
        result = {}
        
        # Attributes
        for key, value in element.attrib.items():
            result[f"@{key}"] = value
        
        # Text content
        if element.text and element.text.strip():
            if len(element) == 0:
                result['#text'] = element.text.strip()
        
        # Children
        for child in element:
            child_data = self._xml_element_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result
    
    async def _parse_pdf(self, content: bytes, url: str) -> List[Dict[str, Any]]:
        """Parse PDF content - extract text and tables."""
        records = []
        
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, skipping PDF parsing")
            return [{'url': url, 'error': 'pdfplumber not installed', '_source_format': 'pdf'}]
        
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text
                    text = page.extract_text()
                    
                    # Extract tables
                    tables = page.extract_tables()
                    
                    record = {
                        'url': url,
                        'page': page_num + 1,
                        'text': text,
                        'tables_count': len(tables),
                        '_source_format': 'pdf'
                    }
                    
                    if tables:
                        for i, table in enumerate(tables):
                            if table and len(table) > 1:
                                # First row as headers
                                headers = [str(h) if h else f"col_{j}" for j, h in enumerate(table[0])]
                                for row in table[1:]:
                                    table_record = record.copy()
                                    table_record['table_index'] = i
                                    table_record['table_data'] = dict(zip(headers, row))
                                    records.append(table_record)
                    else:
                        records.append(record)
        
        except Exception as e:
            logger.error("PDF parsing failed", url=url, error=str(e))
            records.append({'url': url, 'error': str(e), '_source_format': 'pdf'})
        
        return records


class RegulatoryConnector(BaseConnector):
    """Specialized connector for regulatory publications (IDX, OJK, BI, BPS, etc.)."""
    
    @property
    def connector_type(self) -> str:
        return "regulatory"
    
    async def _fetch_data(self) -> FetchResult:
        config = self.source.config
        domain = self.source.domain
        
        # Domain-specific handling
        if 'idx.co.id' in domain:
            return await self._fetch_idx(config)
        elif 'ojk.go.id' in domain:
            return await self._fetch_ojk(config)
        elif 'bi.go.id' in domain:
            return await self._fetch_bi(config)
        elif 'bps.go.id' in domain:
            return await self._fetch_bps(config)
        elif 'kemenkeu.go.id' in domain:
            return await self._fetch_kemenkeu(config)
        else:
            # Generic public website scraping
            return await self._fetch_generic(config)
    
    async def _fetch_idx(self, config: SourceConfiguration) -> FetchResult:
        """Fetch from IDX (Indonesia Stock Exchange)."""
        records = []
        
        for endpoint_name, endpoint_path in config.endpoints.items():
            try:
                url = f"{config.base_url.rstrip('/')}{endpoint_path}"
                params = dict(config.query_params)
                
                response = await self._fetch_with_retry(url, params=params)
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract records based on endpoint
                    extracted = self._extract_idx_records(data, endpoint_name)
                    for record in extracted:
                        record['_idx_endpoint'] = endpoint_name
                        record['_source_format'] = 'idx_api'
                    records.extend(extracted)
                
            except Exception as e:
                logger.warning("IDX endpoint failed", endpoint=endpoint_name, error=str(e))
        
        records = self._deduplicate_records(records)
        
        return FetchResult(
            success=True,
            data=records,
            records_count=len(records),
            source_id=self.source.source_id,
            metadata={"endpoints_fetched": len(config.endpoints)}
        )
    
    def _extract_idx_records(self, data: Any, endpoint: str) -> List[Dict[str, Any]]:
        """Extract records from IDX API response."""
        records = []
        
        # IDX API typically returns {data: [...], ...} or similar
        if isinstance(data, dict):
            for key in ['data', 'results', 'items', 'records', 'ListedCompanies', 'StockSummary', 'FinancialReports', 'CorporateActions', 'Indices']:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Try any list value
            for key, value in data.items():
                if isinstance(value, list) and value:
                    return value
        elif isinstance(data, list):
            return data
        
        return []
    
    async def _fetch_ojk(self, config: SourceConfiguration) -> FetchResult:
        """Fetch from OJK (Financial Services Authority)."""
        # OJK primarily publishes HTML pages and PDFs
        # Use document connector for PDFs, scrape HTML for listings
        records = []
        
        for endpoint_name, endpoint_path in config.endpoints.items():
            try:
                url = f"{config.base_url.rstrip('/')}{endpoint_path}"
                response = await self._fetch_with_retry(url)
                
                if response.status == 200:
                    content = await response.text()
                    
                    # Check for PDF links
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Extract links to PDFs, CSVs, etc.
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if any(href.lower().endswith(ext) for ext in ['.pdf', '.csv', '.xlsx', '.xls', '.json']):
                            full_url = urljoin(url, href)
                            records.append({
                                'title': link.get_text(strip=True),
                                'url': full_url,
                                'source_page': url,
                                'endpoint': endpoint_name,
                                '_source_format': 'ojk_listing'
                            })
            
            except Exception as e:
                logger.warning("OJK endpoint failed", endpoint=endpoint_name, error=str(e))
        
        records = self._deduplicate_records(records)
        
        return FetchResult(
            success=True,
            data=records,
            records_count=len(records),
            source_id=self.source.source_id,
            metadata={"endpoints_scraped": len(config.endpoints)}
        )
    
    async def _fetch_bi(self, config: SourceConfiguration) -> FetchResult:
        """Fetch from Bank Indonesia."""
        records = []
        
        for endpoint_name, endpoint_path in config.endpoints.items():
            try:
                url = f"{config.base_url.rstrip('/')}{endpoint_path}"
                params = dict(config.query_params)
                
                response = await self._fetch_with_retry(url, params=params)
                
                if response.status == 200:
                    data = await response.json()
                    extracted = self._extract_bi_records(data, endpoint_name)
                    for record in extracted:
                        record['_bi_endpoint'] = endpoint_name
                        record['_source_format'] = 'bi_api'
                    records.extend(extracted)
            
            except Exception as e:
                logger.warning("BI endpoint failed", endpoint=endpoint_name, error=str(e))
        
        records = self._deduplicate_records(records)
        
        return FetchResult(
            success=True,
            data=records,
            records_count=len(records),
            source_id=self.source.source_id,
            metadata={"endpoints_fetched": len(config.endpoints)}
        )
    
    def _extract_bi_records(self, data: Any, endpoint: str) -> List[Dict[str, Any]]:
        """Extract records from Bank Indonesia API response."""
        if isinstance(data, dict):
            for key in ['data', 'results', 'items', 'records', 'content']:
                if key in data and isinstance(data[key], list):
                    return data[key]
        elif isinstance(data, list):
            return data
        return []
    
    async def _fetch_bps(self, config: SourceConfiguration) -> FetchResult:
        """Fetch from BPS (Statistics Indonesia)."""
        records = []
        
        for endpoint_name, endpoint_path in config.endpoints.items():
            try:
                url = f"{config.base_url.rstrip('/')}{endpoint_path}"
                params = dict(config.query_params)
                
                response = await self._fetch_with_retry(url, params=params)
                
                if response.status == 200:
                    data = await response.json()
                    extracted = self._extract_bps_records(data, endpoint_name)
                    for record in extracted:
                        record['_bps_endpoint'] = endpoint_name
                        record['_source_format'] = 'bps_api'
                    records.extend(extracted)
            
            except Exception as e:
                logger.warning("BPS endpoint failed", endpoint=endpoint_name, error=str(e))
        
        records = self._deduplicate_records(records)
        
        return FetchResult(
            success=True,
            data=records,
            records_count=len(records),
            source_id=self.source.source_id,
            metadata={"endpoints_fetched": len(config.endpoints)}
        )
    
    def _extract_bps_records(self, data: Any, endpoint: str) -> List[Dict[str, Any]]:
        """Extract records from BPS API response."""
        if isinstance(data, dict):
            for key in ['data', 'results', 'items', 'records', 'Data']:
                if key in data and isinstance(data[key], list):
                    return data[key]
        elif isinstance(data, list):
            return data
        return []
    
    async def _fetch_kemenkeu(self, config: SourceConfiguration) -> FetchResult:
        """Fetch from Ministry of Finance."""
        # Similar to OJK - mostly HTML/PDF
        return await self._fetch_ojk(config)  # Reuse generic scraping
    
    async def _fetch_generic(self, config: SourceConfiguration) -> FetchResult:
        """Generic public website scraping."""
        records = []
        
        for endpoint_name, endpoint_path in config.endpoints.items():
            try:
                url = f"{config.base_url.rstrip('/')}{endpoint_path}"
                response = await self._fetch_with_retry(url)
                
                if response.status == 200:
                    content = await response.text()
                    
                    # Extract structured data (JSON-LD, microdata, tables)
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Extract tables
                    for table in soup.find_all('table'):
                        table_data = self._parse_html_table(table)
                        if table_data:
                            for row in table_data:
                                row['source_table_url'] = url
                                row['endpoint'] = endpoint_name
                                row['_source_format'] = 'html_table'
                                records.append(row)
                    
                    # Extract JSON-LD structured data
                    for script in soup.find_all('script', type='application/ld+json'):
                        try:
                            ld_data = json.loads(script.string)
                            if isinstance(ld_data, dict):
                                ld_data['_source_format'] = 'json_ld'
                                ld_data['source_url'] = url
                                records.append(ld_data)
                            elif isinstance(ld_data, list):
                                for item in ld_data:
                                    item['_source_format'] = 'json_ld'
                                    item['source_url'] = url
                                    records.append(item)
                        except:
                            pass
            
            except Exception as e:
                logger.warning("Generic scraping failed", endpoint=endpoint_name, error=str(e))
        
        records = self._deduplicate_records(records)
        
        return FetchResult(
            success=True,
            data=records,
            records_count=len(records),
            source_id=self.source.source_id,
            metadata={"endpoints_scraped": len(config.endpoints)}
        )
    
    def _parse_html_table(self, table) -> List[Dict[str, Any]]:
        """Parse HTML table to list of records."""
        rows = table.find_all('tr')
        if not rows:
            return []
        
        # Get headers from first row
        header_row = rows[0]
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        if not headers:
            return []
        
        records = []
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) == len(headers):
                values = [cell.get_text(strip=True) for cell in cells]
                records.append(dict(zip(headers, values)))
        
        return records


# Connector factory
def create_connector(source: Source, registry: SourceRegistry, **kwargs) -> BaseConnector:
    """Factory function to create appropriate connector for a source."""
    config = ConnectorConfig(source=source, **kwargs)
    
    access_method = source.access_method
    
    if access_method == AccessMethod.REST_API:
        return RestApiConnector(config, registry)
    elif access_method in [AccessMethod.RSS_FEED, AccessMethod.ATOM_FEED]:
        return RssFeedConnector(config, registry)
    elif access_method == AccessMethod.SITEMAP:
        return SitemapConnector(config, registry)
    elif access_method in [AccessMethod.PDF_DOCUMENT, AccessMethod.CSV_FILE, AccessMethod.XLSX_FILE, AccessMethod.JSON_FILE]:
        return DocumentConnector(config, registry)
    elif access_method == AccessMethod.PUBLIC_WEBSITE and source.data_category.value in ['regulatory', 'investor_relations']:
        return RegulatoryConnector(config, registry)
    else:
        # Default to REST API
        return RestApiConnector(config, registry)


async def fetch_from_source(source: Source, registry: SourceRegistry, **kwargs) -> FetchResult:
    """Convenience function to fetch data from a source."""
    connector = create_connector(source, registry, **kwargs)
    async with connector:
        return await connector.fetch()


if __name__ == "__main__":
    async def test():
        from erin.data_core import SourceRegistry
        registry = SourceRegistry()
        await registry.initialize()
        
        # Test with a macro source
        sources = await registry.list_sources(data_category="macroeconomic")
        if sources:
            source = sources[0]
            print(f"Testing connector for: {source.name}")
            
            result = await fetch_from_source(source, registry)
            print(f"Success: {result.success}")
            print(f"Records: {result.records_count}")
            if result.error:
                print(f"Error: {result.error}")
    
    asyncio.run(test())

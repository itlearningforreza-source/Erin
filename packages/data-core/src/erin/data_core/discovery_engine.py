"""
ERIN Data Core - Autonomous Discovery Engine
Discovers new financial data sources from official APIs, RSS feeds, sitemaps, and regulatory publications.
"""

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional, List, Dict, Set, Callable, Awaitable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import aiohttp
import feedparser
import structlog
from bs4 import BeautifulSoup

from erin.data_core.source_registry import (
    Source,
    SourceRegistry,
    DataCategory,
    AccessMethod,
    AuthenticationType,
    LicensingClassification,
    OperationalStatus,
    SourceConfiguration,
    INDONESIA_DEFAULT_SOURCES
)

logger = structlog.get_logger(__name__)


@dataclass
class DiscoveryResult:
    """Result of a source discovery operation."""
    source: Source
    confidence: float  # 0.0 - 1.0
    evidence: List[str]  # Evidence supporting the discovery
    discovery_method: str
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requires_verification: bool = True


class DiscoveryMethod:
    """Constants for discovery methods."""
    RSS_FEED = "auto_rss"
    ATOM_FEED = "auto_atom"
    SITEMAP = "auto_sitemap"
    API_DOCS = "auto_api_docs"
    REGULATORY_LISTING = "auto_regulatory_listing"
    REFERRAL = "referral"
    MANUAL = "manual"


class DiscoveryEngine:
    """Autonomous source discovery engine."""
    
    def __init__(
        self,
        registry: SourceRegistry,
        max_concurrent: int = 5,
        request_timeout: int = 30,
        user_agent: str = "ERIN-Discovery/1.0 (+https://erin.local)"
    ):
        self.registry = registry
        self.max_concurrent = max_concurrent
        self.request_timeout = request_timeout
        self.user_agent = user_agent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None
        self._discovery_callbacks: List[Callable[[DiscoveryResult], Awaitable[None]]] = []
        
        # Known patterns for source identification
        self._api_patterns = [
            r'/api/',
            r'/v\d+/',
            r'/rest/',
            r'/graphql',
            r'\.json$',
            r'/swagger',
            r'/openapi',
            r'/docs'
        ]
        self._rss_patterns = [
            r'/rss',
            r'/feed',
            r'\.xml$',
            r'/atom'
        ]
        self._financial_keywords = [
            'financial', 'market', 'stock', 'bond', 'equity', 'index',
            'exchange', 'trading', 'price', 'quote', 'ticker', 'symbol',
            'company', 'corporate', 'earnings', 'revenue', 'profit',
            'balance sheet', 'income statement', 'cash flow',
            'dividend', 'split', 'merger', 'acquisition',
            'regulation', 'filing', 'disclosure', 'report',
            'macro', 'economic', 'inflation', 'gdp', 'interest rate',
            'exchange rate', 'currency', 'commodity', 'derivative'
        ]
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            headers={'User-Agent': self.user_agent}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def add_discovery_callback(self, callback: Callable[[DiscoveryResult], Awaitable[None]]):
        """Add a callback to be notified of new discoveries."""
        self._discovery_callbacks.append(callback)
    
    async def _notify_discovery(self, result: DiscoveryResult):
        """Notify all callbacks of a discovery."""
        for callback in self._discovery_callbacks:
            try:
                await callback(result)
            except Exception as e:
                logger.error("Discovery callback failed", error=str(e))
    
    async def _fetch(self, url: str) -> Optional[str]:
        """Fetch content from URL with error handling."""
        if not self._session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        async with self._semaphore:
            try:
                async with self._session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning("Fetch failed", url=url, status=response.status)
                        return None
            except asyncio.TimeoutError:
                logger.warning("Fetch timeout", url=url)
                return None
            except Exception as e:
                logger.warning("Fetch error", url=url, error=str(e))
                return None
    
    async def discover_from_rss(self, feed_url: str, parent_source_id: Optional[str] = None) -> List[DiscoveryResult]:
        """Discover sources from an RSS/Atom feed."""
        results = []
        
        content = await self._fetch(feed_url)
        if not content:
            return results
        
        try:
            feed = feedparser.parse(content)
            
            # Check if this is a financial feed
            feed_title = feed.feed.get('title', '').lower()
            feed_description = feed.feed.get('description', '').lower()
            
            if not any(kw in feed_title + ' ' + feed_description for kw in self._financial_keywords):
                logger.info("Feed doesn't appear financial", url=feed_url)
                return results
            
            # Extract links from feed entries
            for entry in feed.entries[:50]:  # Limit to recent 50
                link = entry.get('link', '')
                if not link:
                    continue
                
                # Parse the link domain
                parsed = urlparse(link)
                domain = parsed.netloc.lower()
                
                # Skip if already known
                existing = await self.registry.get_by_domain_and_name(domain, f"{domain} Feed")
                if existing:
                    continue
                
                # Create source candidate
                source = Source(
                    name=f"{domain} Feed",
                    domain=domain,
                    data_category=self._categorize_from_content(feed_title + ' ' + feed_description),
                    access_method=AccessMethod.RSS_FEED,
                    authentication=AuthenticationType.NONE,
                    licensing=LicensingClassification.UNKNOWN,
                    config=SourceConfiguration(
                        base_url=f"{parsed.scheme}://{domain}",
                        endpoints={"feed": parsed.path},
                        rate_limit_rpm=30
                    ),
                    update_frequency="hourly",
                    reliability_score=0.5,
                    operational_status=OperationalStatus.UNKNOWN,
                    description=f"Discovered via RSS feed: {feed_title}",
                    tags=["auto_discovered", "rss", domain],
                    discovered_by="discovery_engine",
                    discovery_method=DiscoveryMethod.RSS_FEED,
                    parent_source_id=parent_source_id
                )
                
                confidence = self._calculate_confidence(source, entry.get('summary', ''))
                evidence = [f"Found in RSS feed: {feed_url}", f"Entry title: {entry.get('title', '')[:100]}"]
                
                results.append(DiscoveryResult(
                    source=source,
                    confidence=confidence,
                    evidence=evidence,
                    discovery_method=DiscoveryMethod.RSS_FEED
                ))
        
        except Exception as e:
            logger.error("RSS parsing failed", url=feed_url, error=str(e))
        
        return results
    
    async def discover_from_sitemap(self, sitemap_url: str, parent_source_id: Optional[str] = None) -> List[DiscoveryResult]:
        """Discover sources from a sitemap."""
        results = []
        
        content = await self._fetch(sitemap_url)
        if not content:
            return results
        
        try:
            root = ET.fromstring(content)
            namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            urls = []
            for url_elem in root.findall('.//sm:url', namespace):
                loc = url_elem.find('sm:loc', namespace)
                if loc is not None and loc.text:
                    urls.append(loc.text)
            
            # Also check for sitemap index
            for sitemap_elem in root.findall('.//sm:sitemap', namespace):
                loc = sitemap_elem.find('sm:loc', namespace)
                if loc is not None and loc.text:
                    # Recursively discover from sub-sitemap
                    sub_results = await self.discover_from_sitemap(loc.text, parent_source_id)
                    results.extend(sub_results)
            
            # Analyze URLs for financial content patterns
            financial_paths = []
            for url in urls[:200]:  # Limit analysis
                parsed = urlparse(url)
                path = parsed.path.lower()
                
                # Check for financial content patterns
                for kw in self._financial_keywords:
                    if kw in path:
                        financial_paths.append(url)
                        break
            
            # Group by domain
            domain_paths: Dict[str, List[str]] = {}
            for url in financial_paths:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                if domain not in domain_paths:
                    domain_paths[domain] = []
                domain_paths[domain].append(url)
            
            # Create source candidates for domains with financial content
            for domain, paths in domain_paths.items():
                existing = await self.registry.get_by_domain_and_name(domain, f"{domain} Sitemap")
                if existing:
                    continue
                
                # Determine primary category from paths
                category = DataCategory.ALTERNATIVE
                for path in paths[:10]:
                    cat = self._categorize_from_content(path)
                    if cat != DataCategory.ALTERNATIVE:
                        category = cat
                        break
                
                source = Source(
                    name=f"{domain} Sitemap",
                    domain=domain,
                    data_category=category,
                    access_method=AccessMethod.SITEMAP,
                    authentication=AuthenticationType.NONE,
                    licensing=LicensingClassification.UNKNOWN,
                    config=SourceConfiguration(
                        base_url=f"https://{domain}",
                        endpoints={"sitemap": "/sitemap.xml"},
                        rate_limit_rpm=20
                    ),
                    update_frequency="daily",
                    reliability_score=0.4,
                    operational_status=OperationalStatus.UNKNOWN,
                    description=f"Discovered via sitemap analysis: {len(paths)} financial paths found",
                    tags=["auto_discovered", "sitemap", domain],
                    discovered_by="discovery_engine",
                    discovery_method=DiscoveryMethod.SITEMAP,
                    parent_source_id=parent_source_id
                )
                
                confidence = min(0.7, 0.3 + len(paths) * 0.02)
                evidence = [f"Found in sitemap: {sitemap_url}", f"Financial paths: {len(paths)}", f"Sample: {paths[0] if paths else 'N/A'}"]
                
                results.append(DiscoveryResult(
                    source=source,
                    confidence=confidence,
                    evidence=evidence,
                    discovery_method=DiscoveryMethod.SITEMAP
                ))
        
        except ET.ParseError as e:
            logger.error("Sitemap XML parsing failed", url=sitemap_url, error=str(e))
        except Exception as e:
            logger.error("Sitemap discovery failed", url=sitemap_url, error=str(e))
        
        return results
    
    async def discover_from_api_docs(self, docs_url: str, parent_source_id: Optional[str] = None) -> List[DiscoveryResult]:
        """Discover API endpoints from documentation pages."""
        results = []
        
        content = await self._fetch(docs_url)
        if not content:
            return results
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for API endpoints in documentation
            endpoints = set()
            
            # Check for OpenAPI/Swagger specs
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(pattern in href.lower() for pattern in ['swagger', 'openapi', '.json', '.yaml', '.yml']):
                    endpoints.add(urljoin(docs_url, href))
            
            # Check for code examples with API paths
            for code in soup.find_all(['code', 'pre']):
                text = code.get_text()
                # Look for URL patterns
                for match in re.finditer(r'(https?://[^\s"\'<>]+)', text):
                    url = match.group(1)
                    if any(pattern in url for pattern in ['/api/', '/v1/', '/v2/', '/rest/']):
                        endpoints.add(url)
            
            # Group endpoints by domain
            domain_endpoints: Dict[str, List[str]] = {}
            for endpoint in endpoints:
                parsed = urlparse(endpoint)
                domain = parsed.netloc.lower()
                if domain not in domain_endpoints:
                    domain_endpoints[domain] = []
                domain_endpoints[domain].append(endpoint)
            
            for domain, eps in domain_endpoints.items():
                existing = await self.registry.get_by_domain_and_name(domain, f"{domain} API")
                if existing:
                    continue
                
                source = Source(
                    name=f"{domain} API",
                    domain=domain,
                    data_category=DataCategory.ALTERNATIVE,
                    access_method=AccessMethod.REST_API,
                    authentication=AuthenticationType.UNKNOWN,
                    licensing=LicensingClassification.UNKNOWN,
                    config=SourceConfiguration(
                        base_url=f"https://{domain}",
                        endpoints={f"endpoint_{i}": ep for i, ep in enumerate(eps[:10])},
                        rate_limit_rpm=60
                    ),
                    update_frequency="unknown",
                    reliability_score=0.4,
                    operational_status=OperationalStatus.UNKNOWN,
                    description=f"Discovered via API documentation: {len(eps)} endpoints found",
                    tags=["auto_discovered", "api_docs", domain],
                    discovered_by="discovery_engine",
                    discovery_method=DiscoveryMethod.API_DOCS,
                    parent_source_id=parent_source_id
                )
                
                confidence = min(0.8, 0.4 + len(eps) * 0.03)
                evidence = [f"Found in API docs: {docs_url}", f"Endpoints: {len(eps)}", f"Sample: {eps[0] if eps else 'N/A'}"]
                
                results.append(DiscoveryResult(
                    source=source,
                    confidence=confidence,
                    evidence=evidence,
                    discovery_method=DiscoveryMethod.API_DOCS
                ))
        
        except Exception as e:
            logger.error("API docs discovery failed", url=docs_url, error=str(e))
        
        return results
    
    async def discover_regulatory_sources(self, base_url: str, parent_source_id: Optional[str] = None) -> List[DiscoveryResult]:
        """Discover sources from regulatory body websites."""
        results = []
        
        content = await self._fetch(base_url)
        if not content:
            return results
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for data/download/API links
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text().lower()
                
                # Keywords indicating data availability
                data_keywords = ['data', 'statistic', 'api', 'download', 'csv', 'xlsx', 'json', 'feed', 'portal', 'dashboard']
                if any(kw in text for kw in data_keywords) or any(kw in href.lower() for kw in data_keywords):
                    links.append(urljoin(base_url, href))
            
            # Also check for specific financial regulators
            domain = urlparse(base_url).netloc.lower()
            
            for link in links[:30]:  # Limit
                try:
                    link_content = await self._fetch(link)
                    if not link_content:
                        continue
                    
                    link_soup = BeautifulSoup(link_content, 'html.parser')
                    link_text = link_soup.get_text().lower()
                    
                    # Determine category from content
                    category = self._categorize_from_content(link_text)
                    
                    # Check if it's an API
                    access_method = AccessMethod.PUBLIC_WEBSITE
                    if any(kw in link_text for kw in ['api', 'rest', 'endpoint', 'swagger', 'openapi']):
                        access_method = AccessMethod.REST_API
                    elif any(kw in link_text for kw in ['rss', 'feed', 'atom']):
                        access_method = AccessMethod.RSS_FEED
                    elif link.endswith('.csv') or 'csv' in link_text:
                        access_method = AccessMethod.CSV_FILE
                    elif link.endswith('.xlsx') or link.endswith('.xls') or 'excel' in link_text:
                        access_method = AccessMethod.XLSX_FILE
                    elif link.endswith('.json'):
                        access_method = AccessMethod.JSON_FILE
                    
                    source = Source(
                        name=f"{domain} - {category.value.replace('_', ' ').title()}",
                        domain=domain,
                        data_category=category,
                        access_method=access_method,
                        authentication=AuthenticationType.NONE,
                        licensing=LicensingClassification.OPEN_DATA,  # Regulatory data typically open
                        config=SourceConfiguration(
                            base_url=f"https://{domain}",
                            endpoints={"data": link},
                            rate_limit_rpm=20
                        ),
                        update_frequency="monthly",
                        reliability_score=0.7,  # Regulatory sources generally reliable
                        operational_status=OperationalStatus.UNKNOWN,
                        description=f"Discovered on regulatory website: {link_text[:200]}",
                        tags=["auto_discovered", "regulatory", domain, category.value],
                        discovered_by="discovery_engine",
                        discovery_method=DiscoveryMethod.REGULATORY_LISTING,
                        parent_source_id=parent_source_id
                    )
                    
                    confidence = 0.6
                    evidence = [f"Found on regulatory site: {base_url}", f"Data page: {link}", f"Content preview: {link_text[:200]}"]
                    
                    results.append(DiscoveryResult(
                        source=source,
                        confidence=confidence,
                        evidence=evidence,
                        discovery_method=DiscoveryMethod.REGULATORY_LISTING
                    ))
                
                except Exception as e:
                    logger.debug("Failed to analyze regulatory link", link=link, error=str(e))
        
        except Exception as e:
            logger.error("Regulatory discovery failed", url=base_url, error=str(e))
        
        return results
    
    def _categorize_from_content(self, content: str) -> DataCategory:
        """Categorize source based on content keywords."""
        content_lower = content.lower()
        
        # Priority-based categorization
        if any(kw in content_lower for kw in ['stock price', 'quote', 'ticker', 'ohlcv', 'intraday', 'market data']):
            return DataCategory.EQUITY_PRICES
        if any(kw in content_lower for kw in ['financial statement', 'balance sheet', 'income statement', 'cash flow', 'earnings', 'revenue', 'fundamental']):
            return DataCategory.EQUITY_FUNDAMENTALS
        if any(kw in content_lower for kw in ['bond', 'yield curve', 'fixed income', 'treasury', 'corporate bond']):
            return DataCategory.FIXED_INCOME
        if any(kw in content_lower for kw in ['option', 'future', 'derivative', 'volatility', 'greeks', 'strike']):
            return DataCategory.DERIVATIVES
        if any(kw in content_lower for kw in ['gdp', 'inflation', 'cpi', 'ppi', 'unemployment', 'interest rate', 'monetary', 'macro']):
            return DataCategory.MACROECONOMIC
        if any(kw in content_lower for kw in ['news', 'article', 'press release', 'announcement']):
            return DataCategory.NEWS
        if any(kw in content_lower for kw in ['regulation', 'regulatory', 'compliance', 'filing', 'disclosure', 'sec', 'ojk']):
            return DataCategory.REGULATORY
        if any(kw in content_lower for kw in ['corporate action', 'dividend', 'split', 'merger', 'acquisition', 'spin-off']):
            return DataCategory.CORPORATE_ACTIONS
        if any(kw in content_lower for kw in ['10-k', '10-q', '8-k', 'annual report', 'quarterly report', 'filing']):
            return DataCategory.COMPANY_FILINGS
        if any(kw in content_lower for kw in ['investor relation', 'shareholder', 'annual meeting', 'proxy']):
            return DataCategory.INVESTOR_RELATIONS
        if any(kw in content_lower for kw in ['index', 'benchmark', 'sector index']):
            return DataCategory.INDICES
        if any(kw in content_lower for kw in ['commodity', 'gold', 'oil', 'crude', 'metal', 'agricultural']):
            return DataCategory.COMMODITIES
        if any(kw in content_lower for kw in ['fx', 'forex', 'exchange rate', 'currency pair']):
            return DataCategory.FX
        if any(kw in content_lower for kw in ['crypto', 'bitcoin', 'ethereum', 'blockchain', 'digital asset']):
            return DataCategory.CRYPTO
        
        return DataCategory.ALTERNATIVE
    
    def _calculate_confidence(self, source: Source, content: str) -> float:
        """Calculate confidence score for a discovered source."""
        score = 0.3  # Base
        
        content_lower = content.lower()
        
        # Boost for financial keywords
        financial_matches = sum(1 for kw in self._financial_keywords if kw in content_lower)
        score += min(0.3, financial_matches * 0.02)
        
        # Boost for known domains
        trusted_domains = ['gov', 'centralbank', 'sec.', 'ojk.', 'bi.', 'bps.', 'kemenkeu.', 'worldbank.', 'imf.', 'fred.']
        if any(t in source.domain for t in trusted_domains):
            score += 0.2
        
        # Boost for HTTPS
        if source.config.base_url.startswith('https://'):
            score += 0.1
        
        return min(1.0, score)
    
    async def run_discovery_cycle(self, seed_urls: Optional[List[str]] = None) -> List[DiscoveryResult]:
        """Run a full discovery cycle from seed URLs."""
        all_results = []
        
        # Default seed URLs for Indonesia financial ecosystem
        if seed_urls is None:
            seed_urls = [
                "https://www.idx.co.id/sitemap.xml",
                "https://www.ojk.go.id/sitemap.xml",
                "https://www.bi.go.id/sitemap.xml",
                "https://www.bps.go.id/sitemap.xml",
                "https://www.kemenkeu.go.id/sitemap.xml",
                "https://api.stlouisfed.org/fred/sitemap.xml",
                "https://api.worldbank.org/sitemap.xml",
                "https://dataservices.imf.org/sitemap.xml"
            ]
        
        # Discover from sitemaps
        for url in seed_urls:
            try:
                results = await self.discover_from_sitemap(url)
                all_results.extend(results)
                for r in results:
                    await self._notify_discovery(r)
            except Exception as e:
                logger.error("Sitemap discovery cycle failed", url=url, error=str(e))
        
        # Discover from known RSS feeds
        rss_feeds = [
            "https://www.idx.co.id/rss.xml",
            "https://www.ojk.go.id/rss.xml",
            "https://www.bi.go.id/rss.xml",
            "https://www.bps.go.id/rss.xml"
        ]
        
        for url in rss_feeds:
            try:
                results = await self.discover_from_rss(url)
                all_results.extend(results)
                for r in results:
                    await self._notify_discovery(r)
            except Exception as e:
                logger.debug("RSS discovery cycle failed", url=url, error=str(e))
        
        # Discover from regulatory sites
        regulatory_sites = [
            "https://www.ojk.go.id",
            "https://www.bi.go.id",
            "https://www.bps.go.id",
            "https://www.kemenkeu.go.id"
        ]
        
        for url in regulatory_sites:
            try:
                results = await self.discover_regulatory_sources(url)
                all_results.extend(results)
                for r in results:
                    await self._notify_discovery(r)
            except Exception as e:
                logger.error("Regulatory discovery cycle failed", url=url, error=str(e))
        
        logger.info("Discovery cycle completed", total_discovered=len(all_results))
        return all_results
    
    async def auto_register_high_confidence(self, results: List[DiscoveryResult], min_confidence: float = 0.7) -> int:
        """Automatically register high-confidence discoveries."""
        registered = 0
        for result in results:
            if result.confidence >= min_confidence:
                try:
                    # Check if already exists
                    existing = await self.registry.get_by_domain_and_name(
                        result.source.domain, result.source.name
                    )
                    if not existing:
                        await self.registry.register(result.source)
                        registered += 1
                        logger.info("Auto-registered source", source_id=result.source.source_id, confidence=result.confidence)
                except Exception as e:
                    logger.warning("Auto-registration failed", source=result.source.name, error=str(e))
        return registered


class SourceMonitor:
    """Monitors existing sources for changes and health."""
    
    def __init__(self, registry: SourceRegistry, check_interval_hours: int = 24):
        self.registry = registry
        self.check_interval_hours = check_interval_hours
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Source monitor started")
    
    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Source monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_sources()
            except Exception as e:
                logger.error("Monitor loop error", error=str(e))
            
            await asyncio.sleep(self.check_interval_hours * 3600)
    
    async def _check_all_sources(self):
        """Check all sources for health and changes."""
        sources = await self.registry.list_sources(operational_status=OperationalStatus.ACTIVE)
        
        for source in sources:
            try:
                await self._check_source(source)
            except Exception as e:
                logger.error("Source check failed", source_id=source.source_id, error=str(e))
    
    async def _check_source(self, source: Source):
        """Check a single source for health and configuration changes."""
        # Check if source is reachable
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(source.config.base_url, headers={'User-Agent': 'ERIN-Monitor/1.0'}) as response:
                    if response.status >= 500:
                        source.operational_status = OperationalStatus.DEGRADED
                        await self.registry.update(source)
                        logger.warning("Source degraded", source_id=source.source_id, status=response.status)
                    elif response.status >= 400:
                        logger.warning("Source returned client error", source_id=source.source_id, status=response.status)
        except asyncio.TimeoutError:
            source.operational_status = OperationalStatus.DEGRADED
            await self.registry.update(source)
            logger.warning("Source timeout", source_id=source.source_id)
        except Exception as e:
            logger.debug("Source health check failed", source_id=source.source_id, error=str(e))
        
        # Check for configuration changes (for API sources)
        if source.access_method == AccessMethod.REST_API:
            await self._check_api_changes(source)
    
    async def _check_api_changes(self, source: Source):
        """Check for API schema/endpoint changes."""
        # This would typically fetch OpenAPI spec and compare
        # For now, just update last_verification
        source.last_verification = datetime.now(timezone.utc)
        await self.registry.update(source)


async def run_discovery(registry: Optional[SourceRegistry] = None) -> List[DiscoveryResult]:
    """Convenience function to run discovery."""
    if registry is None:
        registry = await get_source_registry()
    
    async with DiscoveryEngine(registry) as engine:
        results = await engine.run_discovery_cycle()
        await engine.auto_register_high_confidence(results)
        return results


if __name__ == "__main__":
    async def test():
        from erin.data_core.source_registry import SourceRegistry
        registry = SourceRegistry()
        await registry.initialize()
        
        async with DiscoveryEngine(registry) as engine:
            results = await engine.run_discovery_cycle()
            print(f"Discovered {len(results)} sources")
            for r in results[:5]:
                print(f"  - {r.source.name} ({r.source.domain}) - confidence: {r.confidence:.2f}")
    
    asyncio.run(test())

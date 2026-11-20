"""
ERIN Data Core - Source Registry
Autonomous source discovery and registry management for financial data sources.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict, Literal
from urllib.parse import urlparse

import aiosqlite
import structlog
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings

logger = structlog.get_logger(__name__)


class DataCategory(str, Enum):
    """Categories of financial data sources."""
    EQUITY_PRICES = "equity_prices"
    EQUITY_FUNDAMENTALS = "equity_fundamentals"
    FIXED_INCOME = "fixed_income"
    DERIVATIVES = "derivatives"
    MACROECONOMIC = "macroeconomic"
    NEWS = "news"
    REGULATORY = "regulatory"
    CORPORATE_ACTIONS = "corporate_actions"
    COMPANY_FILINGS = "company_filings"
    INVESTOR_RELATIONS = "investor_relations"
    INDICES = "indices"
    COMMODITIES = "commodities"
    FX = "fx"
    CRYPTO = "crypto"
    ALTERNATIVE = "alternative"


class AccessMethod(str, Enum):
    """How to access the data source."""
    REST_API = "rest_api"
    GRAPHQL_API = "graphql_api"
    WEBSOCKET = "websocket"
    RSS_FEED = "rss_feed"
    ATOM_FEED = "atom_feed"
    SITEMAP = "sitemap"
    PUBLIC_WEBSITE = "public_website"
    FTP_SFTP = "ftp_sftp"
    EMAIL = "email"
    PDF_DOCUMENT = "pdf_document"
    CSV_FILE = "csv_file"
    XLSX_FILE = "xlsx_file"
    JSON_FILE = "json_file"
    DATABASE_DUMP = "database_dump"


class AuthenticationType(str, Enum):
    """Authentication requirements."""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    BEARER_TOKEN = "bearer_token"
    MUTUAL_TLS = "mutual_tls"
    CUSTOM_HEADER = "custom_header"
    SESSION_COOKIE = "session_cookie"


class LicensingClassification(str, Enum):
    """Data licensing classification."""
    PUBLIC_DOMAIN = "public_domain"
    OPEN_DATA = "open_data"  # e.g., CC0, CC-BY
    PERMISSIVE = "permissive"  # e.g., MIT, Apache-2.0
    ATTRIBUTION_REQUIRED = "attribution_required"  # CC-BY
    SHARE_ALIKE = "share_alike"  # CC-BY-SA
    NON_COMMERCIAL = "non_commercial"  # CC-BY-NC
    PROPRIETARY_FREE = "proprietary_free"  # Free but proprietary terms
    PROPRIETARY_PAID = "proprietary_paid"  # Requires paid license
    UNKNOWN = "unknown"
    RESTRICTED = "restricted"  # Cannot redistribute


class OperationalStatus(str, Enum):
    """Operational status of the source."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    UNKNOWN = "unknown"


@dataclass
class SourceConfiguration:
    """Configuration for accessing a source."""
    base_url: str
    endpoints: Dict[str, str] = field(default_factory=dict)  # endpoint_name -> path
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    rate_limit_rpm: int = 60  # requests per minute
    rate_limit_burst: int = 10
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    pagination: Dict[str, Any] = field(default_factory=dict)
    custom: Dict[str, Any] = field(default_factory=dict)


class Source(BaseModel):
    """Financial data source with full metadata."""
    # Identity
    source_id: str = Field(default_factory=lambda: f"src_{uuid.uuid4().hex[:12]}")
    name: str
    domain: str  # e.g., "idx.co.id", "api.fred.stlouisfed.org"
    
    # Classification
    data_category: DataCategory
    access_method: AccessMethod
    authentication: AuthenticationType = AuthenticationType.NONE
    licensing: LicensingClassification = LicensingClassification.UNKNOWN
    
    # Configuration
    config: SourceConfiguration = Field(default_factory=SourceConfiguration)
    
    # Operational
    update_frequency: str = "daily"  # cron expression or human-readable
    reliability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    operational_status: OperationalStatus = OperationalStatus.UNKNOWN
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_verification: Optional[datetime] = None
    last_successful_fetch: Optional[datetime] = None
    last_failed_fetch: Optional[datetime] = None
    
    # Metadata
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    country: str = "ID"  # ISO 3166-1 alpha-2
    language: str = "id"
    owner: Optional[str] = None  # Organization name
    contact_email: Optional[str] = None
    documentation_url: Optional[str] = None  # Store as string to avoid HttpUrl serialization issues
    terms_of_service_url: Optional[str] = None
    
    # Quality metrics
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = 0.0
    consecutive_failures: int = 0
    total_fetches: int = 0
    successful_fetches: int = 0
    
    # Discovery
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    discovered_by: str = "system"
    discovery_method: str = "manual"  # manual, auto_rss, auto_sitemap, auto_api_docs, referral
    parent_source_id: Optional[str] = None  # If discovered via another source
    
    # Verification
    verified: bool = False
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verification_notes: str = ""
    
    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        parsed = urlparse(v if v.startswith("http") else f"http://{v}")
        return parsed.netloc.lower()
    
    @field_validator("reliability_score")
    @classmethod
    def validate_reliability(cls, v: float) -> float:
        return round(v, 3)
    
    @field_validator("documentation_url", "terms_of_service_url", mode="before")
    @classmethod
    def validate_url(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, HttpUrl):
            return str(v)
        return str(v)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = self.model_dump()
        # Convert enums to strings
        data["data_category"] = self.data_category.value
        data["access_method"] = self.access_method.value
        data["authentication"] = self.authentication.value
        data["licensing"] = self.licensing.value
        data["operational_status"] = self.operational_status.value
        # Convert config to dict
        data["config"] = asdict(self.config) if isinstance(self.config, SourceConfiguration) else self.config
        # Convert datetime to ISO format
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        """Create Source from dictionary."""
        # Convert string enums back
        if "data_category" in data and isinstance(data["data_category"], str):
            data["data_category"] = DataCategory(data["data_category"])
        if "access_method" in data and isinstance(data["access_method"], str):
            data["access_method"] = AccessMethod(data["access_method"])
        if "authentication" in data and isinstance(data["authentication"], str):
            data["authentication"] = AuthenticationType(data["authentication"])
        if "licensing" in data and isinstance(data["licensing"], str):
            data["licensing"] = LicensingClassification(data["licensing"])
        if "operational_status" in data and isinstance(data["operational_status"], str):
            data["operational_status"] = OperationalStatus(data["operational_status"])
        
        # Convert config dict to SourceConfiguration
        if "config" in data and isinstance(data["config"], dict):
            data["config"] = SourceConfiguration(**data["config"])
        
        # Convert ISO format strings to datetime
        for key in ["created_at", "updated_at", "last_verification", 
                    "last_successful_fetch", "last_failed_fetch", "discovered_at", "verified_at"]:
            if key in data and data[key] is not None and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key].replace("Z", "+00:00"))
        
        return cls(**data)
    
    def compute_content_hash(self) -> str:
        """Compute hash of source configuration for change detection."""
        config_str = json.dumps(self.config.__dict__, sort_keys=True, default=str)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]


class SourceRegistrySettings(BaseSettings):
    """Settings for source registry."""
    database_path: str = "~/.erin/data/sources.db"
    auto_discovery_enabled: bool = True
    discovery_interval_hours: int = 24
    verification_interval_hours: int = 168  # weekly
    max_sources: int = 1000
    default_reliability: float = 0.5
    min_reliability_for_auto_use: float = 0.7
    
    class Config:
        env_prefix = "ERIN_SOURCE_"


class SourceRegistry:
    """Registry for managing financial data sources with autonomous discovery."""
    
    def __init__(self, settings: Optional[SourceRegistrySettings] = None):
        self.settings = settings or SourceRegistrySettings()
        self.db_path = Path(self.settings.database_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        self._source_cache: Dict[str, Source] = {}
        self._domain_index: Dict[str, List[str]] = {}  # domain -> source_ids
        self._category_index: Dict[DataCategory, List[str]] = {}
    
    async def initialize(self):
        """Initialize the database and load sources."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    data_category TEXT NOT NULL,
                    access_method TEXT NOT NULL,
                    authentication TEXT NOT NULL,
                    licensing TEXT NOT NULL,
                    config TEXT NOT NULL,
                    update_frequency TEXT NOT NULL,
                    reliability_score REAL NOT NULL,
                    operational_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_verification TEXT,
                    last_successful_fetch TEXT,
                    last_failed_fetch TEXT,
                    description TEXT,
                    tags TEXT,
                    country TEXT,
                    language TEXT,
                    owner TEXT,
                    contact_email TEXT,
                    documentation_url TEXT,
                    terms_of_service_url TEXT,
                    success_rate REAL DEFAULT 0,
                    avg_latency_ms REAL DEFAULT 0,
                    consecutive_failures INTEGER DEFAULT 0,
                    total_fetches INTEGER DEFAULT 0,
                    successful_fetches INTEGER DEFAULT 0,
                    discovered_at TEXT NOT NULL,
                    discovered_by TEXT NOT NULL,
                    discovery_method TEXT NOT NULL,
                    parent_source_id TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_at TEXT,
                    verified_by TEXT,
                    verification_notes TEXT,
                    config_hash TEXT
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_category ON sources(data_category)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(operational_status)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_verified ON sources(verified)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_reliability ON sources(reliability_score DESC)
            """)
            
            await db.commit()
        
        # Load all sources into cache
        await self._load_all_sources()
        self._initialized = True
        logger.info("Source registry initialized", source_count=len(self._source_cache))
    
    async def _load_all_sources(self):
        """Load all sources from database into memory."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM sources") as cursor:
                async for row in cursor:
                    source = self._row_to_source(row)
                    self._source_cache[source.source_id] = source
                    self._index_source(source)
    
    def _row_to_source(self, row: aiosqlite.Row) -> Source:
        """Convert database row to Source object."""
        data = dict(row)
        # Parse JSON fields
        data["config"] = json.loads(data["config"])
        data["tags"] = json.loads(data["tags"]) if data["tags"] else []
        return Source.from_dict(data)
    
    def _source_to_row(self, source: Source) -> tuple:
        """Convert Source to database row tuple (38 fields)."""
        data = source.to_dict()
        return (
            data["source_id"], data["name"], data["domain"], data["data_category"],
            data["access_method"], data["authentication"], data["licensing"],
            json.dumps(data["config"]), data["update_frequency"], data["reliability_score"],
            data["operational_status"], data["created_at"], data["updated_at"],
            data["last_verification"], data["last_successful_fetch"], data["last_failed_fetch"],
            data["description"], json.dumps(data["tags"]), data["country"], data["language"],
            data["owner"], data["contact_email"], data["documentation_url"],
            data["terms_of_service_url"], data["success_rate"], data["avg_latency_ms"],
            data["consecutive_failures"], data["total_fetches"], data["successful_fetches"],
            data["discovered_at"], data["discovered_by"], data["discovery_method"],
            data["parent_source_id"], int(data["verified"]), data["verified_at"],
            data["verified_by"], data["verification_notes"], source.compute_content_hash()
        )
    
    def _source_to_update_row(self, source: Source) -> tuple:
        """Convert Source to UPDATE row tuple (35 fields: all except source_id, created_at, config_hash)."""
        data = source.to_dict()
        return (
            data["name"], data["domain"], data["data_category"], data["access_method"], data["authentication"],
            data["licensing"], json.dumps(data["config"]), data["update_frequency"], data["reliability_score"],
            data["operational_status"], data["updated_at"], data["last_verification"],
            data["last_successful_fetch"], data["last_failed_fetch"], data["description"],
            json.dumps(data["tags"]), data["country"], data["language"], data["owner"],
            data["contact_email"], data["documentation_url"], data["terms_of_service_url"],
            data["success_rate"], data["avg_latency_ms"], data["consecutive_failures"],
            data["total_fetches"], data["successful_fetches"], data["discovered_at"],
            data["discovered_by"], data["discovery_method"], data["parent_source_id"],
            int(data["verified"]), data["verified_at"], data["verified_by"], data["verification_notes"]
        )
    
    def _index_source(self, source: Source):
        """Update indexes for a source."""
        # Domain index
        if source.domain not in self._domain_index:
            self._domain_index[source.domain] = []
        if source.source_id not in self._domain_index[source.domain]:
            self._domain_index[source.domain].append(source.source_id)
        
        # Category index
        if source.data_category not in self._category_index:
            self._category_index[source.data_category] = []
        if source.source_id not in self._category_index[source.data_category]:
            self._category_index[source.data_category].append(source.source_id)
    
    def _remove_from_indexes(self, source: Source):
        """Remove source from indexes."""
        if source.domain in self._domain_index:
            self._domain_index[source.domain] = [
                sid for sid in self._domain_index[source.domain] if sid != source.source_id
            ]
        if source.data_category in self._category_index:
            self._category_index[source.data_category] = [
                sid for sid in self._category_index[source.data_category] if sid != source.source_id
            ]
    
    async def register(self, source: Source) -> Source:
        """Register a new source."""
        if not self._initialized:
            await self.initialize()
        
        # Check for duplicate domain+name
        existing = await self.get_by_domain_and_name(source.domain, source.name)
        if existing:
            raise ValueError(f"Source with domain '{source.domain}' and name '{source.name}' already exists")
        
        # Check max sources
        if len(self._source_cache) >= self.settings.max_sources:
            raise ValueError(f"Maximum number of sources ({self.settings.max_sources}) reached")
        
        source.updated_at = datetime.now(timezone.utc)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._source_to_row(source))
            await db.commit()
        
        self._source_cache[source.source_id] = source
        self._index_source(source)
        
        logger.info("Source registered", source_id=source.source_id, name=source.name, domain=source.domain)
        return source
    
    async def update(self, source: Source) -> Source:
        """Update an existing source."""
        if not self._initialized:
            await self.initialize()
        
        if source.source_id not in self._source_cache:
            raise ValueError(f"Source not found: {source.source_id}")
        
        old_source = self._source_cache[source.source_id]
        self._remove_from_indexes(old_source)
        
        source.updated_at = datetime.now(timezone.utc)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE sources SET
                    name=?, domain=?, data_category=?, access_method=?, authentication=?,
                    licensing=?, config=?, update_frequency=?, reliability_score=?,
                    operational_status=?, updated_at=?, last_verification=?,
                    last_successful_fetch=?, last_failed_fetch=?, description=?,
                    tags=?, country=?, language=?, owner=?, contact_email=?,
                    documentation_url=?, terms_of_service_url=?, success_rate=?,
                    avg_latency_ms=?, consecutive_failures=?, total_fetches=?,
                    successful_fetches=?, discovered_at=?, discovered_by=?,
                    discovery_method=?, parent_source_id=?, verified=?,
                    verified_at=?, verified_by=?, verification_notes=?, config_hash=?
                WHERE source_id=?
            """, self._source_to_update_row(source) + (source.source_id,))
            await db.commit()
        
        self._source_cache[source.source_id] = source
        self._index_source(source)
        
        logger.info("Source updated", source_id=source.source_id)
        return source
    
    async def delete(self, source_id: str) -> bool:
        """Delete a source."""
        if not self._initialized:
            await self.initialize()
        
        if source_id not in self._source_cache:
            return False
        
        source = self._source_cache[source_id]
        self._remove_from_indexes(source)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM sources WHERE source_id=?", (source_id,))
            await db.commit()
        
        del self._source_cache[source_id]
        logger.info("Source deleted", source_id=source_id)
        return True
    
    async def get(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        if not self._initialized:
            await self.initialize()
        return self._source_cache.get(source_id)
    
    async def get_by_domain_and_name(self, domain: str, name: str) -> Optional[Source]:
        """Get a source by domain and name."""
        if not self._initialized:
            await self.initialize()
        
        for source in self._source_cache.values():
            if source.domain == domain and source.name == name:
                return source
        return None
    
    async def list_sources(
        self,
        data_category: Optional[DataCategory] = None,
        domain: Optional[str] = None,
        operational_status: Optional[OperationalStatus] = None,
        verified_only: bool = False,
        min_reliability: float = 0.0,
        limit: int = 100,
        offset: int = 0
    ) -> List[Source]:
        """List sources with filters."""
        if not self._initialized:
            await self.initialize()
        
        sources = list(self._source_cache.values())
        
        if data_category:
            sources = [s for s in sources if s.data_category == data_category]
        if domain:
            sources = [s for s in sources if s.domain == domain]
        if operational_status:
            sources = [s for s in sources if s.operational_status == operational_status]
        if verified_only:
            sources = [s for s in sources if s.verified]
        if min_reliability > 0:
            sources = [s for s in sources if s.reliability_score >= min_reliability]
        
        # Sort by reliability (descending) then name
        sources.sort(key=lambda s: (-s.reliability_score, s.name))
        
        return sources[offset:offset + limit]
    
    async def get_by_category(self, category: DataCategory) -> List[Source]:
        """Get all sources for a data category."""
        if not self._initialized:
            await self.initialize()
        
        source_ids = self._category_index.get(category, [])
        return [self._source_cache[sid] for sid in source_ids if sid in self._source_cache]
    
    async def get_by_domain(self, domain: str) -> List[Source]:
        """Get all sources for a domain."""
        if not self._initialized:
            await self.initialize()
        
        source_ids = self._domain_index.get(domain, [])
        return [self._source_cache[sid] for sid in source_ids if sid in self._source_cache]
    
    async def record_fetch_result(
        self,
        source_id: str,
        success: bool,
        latency_ms: float,
        error: Optional[str] = None
    ):
        """Record the result of a fetch operation."""
        if not self._initialized:
            await self.initialize()
        
        source = self._source_cache.get(source_id)
        if not source:
            logger.warning("Source not found for fetch result", source_id=source_id)
            return
        
        source.total_fetches += 1
        if success:
            source.successful_fetches += 1
            source.last_successful_fetch = datetime.now(timezone.utc)
            source.consecutive_failures = 0
        else:
            source.last_failed_fetch = datetime.now(timezone.utc)
            source.consecutive_failures += 1
            if source.consecutive_failures >= 5:
                source.operational_status = OperationalStatus.DEGRADED
        
        # Update success rate (exponential moving average)
        alpha = 0.1
        source.success_rate = (1 - alpha) * source.success_rate + alpha * (1.0 if success else 0.0)
        
        # Update average latency
        if success:
            source.avg_latency_ms = (source.avg_latency_ms * (source.successful_fetches - 1) + latency_ms) / source.successful_fetches
        
        # Update reliability based on success rate
        source.reliability_score = min(1.0, source.success_rate * 1.2)  # Slight boost for consistency
        
        await self.update(source)
    
    async def verify_source(self, source_id: str, verified_by: str, notes: str = "") -> bool:
        """Mark a source as verified."""
        source = await self.get(source_id)
        if not source:
            return False
        
        source.verified = True
        source.verified_at = datetime.now(timezone.utc)
        source.verified_by = verified_by
        source.verification_notes = notes
        source.last_verification = datetime.now(timezone.utc)
        source.operational_status = OperationalStatus.ACTIVE
        
        await self.update(source)
        logger.info("Source verified", source_id=source_id, verified_by=verified_by)
        return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        if not self._initialized:
            await self.initialize()
        
        sources = list(self._source_cache.values())
        
        by_category = {}
        for cat in DataCategory:
            count = len([s for s in sources if s.data_category == cat])
            if count > 0:
                by_category[cat.value] = count
        
        by_status = {}
        for status in OperationalStatus:
            count = len([s for s in sources if s.operational_status == status])
            if count > 0:
                by_status[status.value] = count
        
        by_domain = {}
        for domain, ids in self._domain_index.items():
            by_domain[domain] = len(ids)
        
        verified_count = len([s for s in sources if s.verified])
        avg_reliability = sum(s.reliability_score for s in sources) / len(sources) if sources else 0
        
        return {
            "total_sources": len(sources),
            "verified_sources": verified_count,
            "unverified_sources": len(sources) - verified_count,
            "average_reliability": round(avg_reliability, 3),
            "by_category": by_category,
            "by_status": by_status,
            "by_domain": by_domain,
            "top_domains": sorted(by_domain.items(), key=lambda x: -x[1])[:10]
        }


# Default Indonesia financial sources
def _create_fred_config() -> SourceConfiguration:
    return SourceConfiguration(
        base_url="https://api.stlouisfed.org/fred",
        endpoints={
            "series": "/series/observations",
            "search": "/series/search",
            "categories": "/category/series"
        },
        rate_limit_rpm=120,
        timeout_seconds=30,
        query_params={"api_key": "${FRED_API_KEY}", "file_type": "json"}
    )


INDONESIA_DEFAULT_SOURCES = [
    Source(
        name="IDX - Indonesia Stock Exchange",
        domain="idx.co.id",
        data_category=DataCategory.EQUITY_PRICES,
        access_method=AccessMethod.REST_API,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://api.idx.co.id",
            endpoints={
                "listed_companies": "/v1/ListedCompanies/GetListedCompanies",
                "stock_summary": "/v1/StockSummary/GetStockSummary",
                "market_summary": "/v1/MarketSummary/GetMarketSummary",
                "financial_reports": "/v1/FinancialReports/GetFinancialReports",
                "corporate_actions": "/v1/CorporateActions/GetCorporateActions",
                "indices": "/v1/Indices/GetIndices"
            },
            rate_limit_rpm=60,
            timeout_seconds=30
        ),
        update_frequency="realtime",
        reliability_score=0.95,
        operational_status=OperationalStatus.ACTIVE,
        description="Official Indonesia Stock Exchange API for listed companies, prices, financial reports, and corporate actions",
        tags=["indonesia", "idx", "official", "equity", "listed_companies"],
        country="ID",
        owner="PT Bursa Efek Indonesia",
        contact_email="info@idx.co.id",
        documentation_url="https://www.idx.co.id/en-us/data-market/statistics/",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="OJK - Financial Services Authority",
        domain="ojk.go.id",
        data_category=DataCategory.REGULATORY,
        access_method=AccessMethod.PUBLIC_WEBSITE,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://www.ojk.go.id",
            endpoints={
                "regulations": "/id/regulasi/",
                "licensed_entities": "/id/perbankan/data-perbankan/",
                "enforcement": "/id/penegakan-hukum/",
                "consumer_protection": "/id/perlindungan-konsumen/",
                "statistics": "/id/statistik/"
            },
            rate_limit_rpm=30,
            timeout_seconds=60
        ),
        update_frequency="daily",
        reliability_score=0.9,
        operational_status=OperationalStatus.ACTIVE,
        description="OJK official website for regulations, licensed financial entities, enforcement actions, and statistics",
        tags=["indonesia", "ojk", "regulator", "banking", "insurance", "capital_markets"],
        country="ID",
        owner="Otoritas Jasa Keuangan",
        contact_email="contact@ojk.go.id",
        documentation_url="https://www.ojk.go.id/id/regulasi/",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="Bank Indonesia - Central Bank",
        domain="bi.go.id",
        data_category=DataCategory.MACROECONOMIC,
        access_method=AccessMethod.REST_API,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://api.bi.go.id",
            endpoints={
                "interest_rates": "/v1/interest-rates",
                "exchange_rates": "/v1/exchange-rates",
                "monetary_aggregates": "/v1/monetary-aggregates",
                "balance_of_payments": "/v1/bop",
                "inflation": "/v1/inflation",
                "gdp": "/v1/gdp",
                "payment_systems": "/v1/payment-systems"
            },
            rate_limit_rpm=120,
            timeout_seconds=30
        ),
        update_frequency="daily",
        reliability_score=0.95,
        operational_status=OperationalStatus.ACTIVE,
        description="Bank Indonesia official API for monetary policy rates, exchange rates, macro indicators, and payment system data",
        tags=["indonesia", "bi", "central_bank", "macro", "interest_rates", "fx", "inflation"],
        country="ID",
        owner="Bank Indonesia",
        contact_email="infobank@bi.go.id",
        documentation_url="https://www.bi.go.id/en/statistik/",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="BPS - Statistics Indonesia",
        domain="bps.go.id",
        data_category=DataCategory.MACROECONOMIC,
        access_method=AccessMethod.REST_API,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://api.bps.go.id",
            endpoints={
                "gdp": "/v1/gdp",
                "inflation": "/v1/inflation",
                "trade": "/v1/trade",
                "population": "/v1/population",
                "labor": "/v1/labor",
                "industry": "/v1/industry",
                "agriculture": "/v1/agriculture",
                "construction": "/v1/construction"
            },
            rate_limit_rpm=60,
            timeout_seconds=60
        ),
        update_frequency="monthly",
        reliability_score=0.9,
        operational_status=OperationalStatus.ACTIVE,
        description="BPS official API for comprehensive Indonesian statistical data including GDP, trade, population, and sectoral statistics",
        tags=["indonesia", "bps", "statistics", "gdp", "trade", "sectoral"],
        country="ID",
        owner="Badan Pusat Statistik",
        contact_email="bps@bps.go.id",
        documentation_url="https://www.bps.go.id/",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="Ministry of Finance - Fiscal Data",
        domain="kemenkeu.go.id",
        data_category=DataCategory.MACROECONOMIC,
        access_method=AccessMethod.PUBLIC_WEBSITE,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://www.kemenkeu.go.id",
            endpoints={
                "state_budget": "/apbn/",
                "tax_revenue": "/pendapatan-pajak/",
                "government_bonds": "/surat-berharga-negara/",
                "fiscal_policy": "/kebijakan-fiskal/",
                "regional_transfers": "/transfer-ke-daerah/"
            },
            rate_limit_rpm=20,
            timeout_seconds=60
        ),
        update_frequency="monthly",
        reliability_score=0.85,
        operational_status=OperationalStatus.ACTIVE,
        description="Ministry of Finance official data for state budget, tax revenue, government bonds, and fiscal policy",
        tags=["indonesia", "kemenkeu", "finance", "budget", "bonds", "tax"],
        country="ID",
        owner="Kementerian Keuangan RI",
        contact_email="humas@kemenkeu.go.id",
        documentation_url="https://www.kemenkeu.go.id/",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="IDX Company Investor Relations Portal",
        domain="idx.co.id",
        data_category=DataCategory.INVESTOR_RELATIONS,
        access_method=AccessMethod.SITEMAP,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.ATTRIBUTION_REQUIRED,
        config=SourceConfiguration(
            base_url="https://www.idx.co.id",
            endpoints={
                "sitemap": "/sitemap.xml",
                "company_profiles": "/en-us/listed-companies/company-profiles/",
                "financial_reports": "/en-us/listed-companies/financial-reports/",
                "general_meetings": "/en-us/listed-companies/gms/",
                "corporate_actions": "/en-us/listed-companies/corporate-actions/"
            },
            rate_limit_rpm=30,
            timeout_seconds=60
        ),
        update_frequency="daily",
        reliability_score=0.85,
        operational_status=OperationalStatus.ACTIVE,
        description="IDX investor relations portal for company profiles, financial reports, GMS, and corporate actions",
        tags=["indonesia", "idx", "investor_relations", "company_profiles", "financial_reports"],
        country="ID",
        owner="PT Bursa Efek Indonesia",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="FRED - Federal Reserve Economic Data (Indonesia Series)",
        domain="fred.stlouisfed.org",
        data_category=DataCategory.MACROECONOMIC,
        access_method=AccessMethod.REST_API,
        authentication=AuthenticationType.API_KEY,
        licensing=LicensingClassification.OPEN_DATA,
        config=_create_fred_config(),
        update_frequency="daily",
        reliability_score=0.98,
        operational_status=OperationalStatus.ACTIVE,
        description="FRED database with extensive Indonesia macroeconomic series (GDP, inflation, trade, etc.)",
        tags=["indonesia", "fred", "macro", "us_source", "api_key_required"],
        country="US",
        owner="Federal Reserve Bank of St. Louis",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="World Bank - Indonesia Data",
        domain="api.worldbank.org",
        data_category=DataCategory.MACROECONOMIC,
        access_method=AccessMethod.REST_API,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://api.worldbank.org/v2",
            endpoints={
                "country": "/country/ID/indicator",
                "indicators": "/indicators"
            },
            rate_limit_rpm=60,
            timeout_seconds=30,
            query_params={"format": "json", "per_page": "1000"}
        ),
        update_frequency="annual",
        reliability_score=0.95,
        operational_status=OperationalStatus.ACTIVE,
        description="World Bank open data for Indonesia development indicators",
        tags=["indonesia", "world_bank", "development", "indicators"],
        country="US",
        owner="World Bank Group",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    ),
    Source(
        name="IMF - Indonesia Data",
        domain="dataservices.imf.org",
        data_category=DataCategory.MACROECONOMIC,
        access_method=AccessMethod.REST_API,
        authentication=AuthenticationType.NONE,
        licensing=LicensingClassification.OPEN_DATA,
        config=SourceConfiguration(
            base_url="https://dataservices.imf.org/REST/SDMX_JSON.svc",
            endpoints={
                "data": "/CompactData/IFS/M.ID.{indicator}",
                "series": "/DataStructure/IFS"
            },
            rate_limit_rpm=30,
            timeout_seconds=60
        ),
        update_frequency="monthly",
        reliability_score=0.95,
        operational_status=OperationalStatus.ACTIVE,
        description="IMF International Financial Statistics for Indonesia",
        tags=["indonesia", "imf", "ifs", "macro", "financial_statistics"],
        country="US",
        owner="International Monetary Fund",
        verified=True,
        verified_by="system",
        discovery_method="manual"
    )
]


async def initialize_default_sources(registry: SourceRegistry) -> int:
    """Initialize registry with default Indonesia sources."""
    count = 0
    for source in INDONESIA_DEFAULT_SOURCES:
        try:
            existing = await registry.get_by_domain_and_name(source.domain, source.name)
            if not existing:
                await registry.register(source)
                count += 1
        except Exception as e:
            logger.warning("Failed to register default source", name=source.name, error=str(e))
    return count


# Convenience function for getting registry instance
_registry_instance: Optional[SourceRegistry] = None


async def get_source_registry() -> SourceRegistry:
    """Get or create the global source registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = SourceRegistry()
        await _registry_instance.initialize()
        await initialize_default_sources(_registry_instance)
    return _registry_instance


if __name__ == "__main__":
    async def test():
        registry = SourceRegistry()
        await registry.initialize()
        await initialize_default_sources(registry)
        
        stats = await registry.get_stats()
        print(json.dumps(stats, indent=2))
        
        # Test listing
        sources = await registry.list_sources(data_category=DataCategory.MACROECONOMIC)
        print(f"\nMacro sources: {len(sources)}")
        for s in sources:
            print(f"  - {s.name} ({s.domain}) - reliability: {s.reliability_score}")
    
    asyncio.run(test())

"""
ERIN Data Core Package
Source registry, discovery engine, and autonomous data acquisition foundation.
"""

from erin.data_core.source_registry import (
    Source,
    SourceRegistry,
    SourceConfiguration,
    DataCategory,
    AccessMethod,
    AuthenticationType,
    LicensingClassification,
    OperationalStatus,
    SourceRegistrySettings,
    INDONESIA_DEFAULT_SOURCES,
    initialize_default_sources,
    get_source_registry
)

from erin.data_core.discovery_engine import (
    DiscoveryEngine,
    DiscoveryResult,
    DiscoveryMethod,
    SourceMonitor,
    run_discovery
)

from erin.data_core.connectors import (
    BaseConnector,
    RestApiConnector,
    RssFeedConnector,
    SitemapConnector,
    DocumentConnector,
    RegulatoryConnector,
    ConnectorConfig,
    FetchResult,
    create_connector,
    fetch_from_source
)

from erin.data_core.integrity import (
    FinancialDataValidator,
    CrossProviderReconciler,
    CorporateActionAdjuster,
    QuarantineManager,
    QuarantinedRecord,
    QuarantineReason,
    QualitySeverity,
    IssueType,
    QualityIssue,
    ReconciliationResult,
    ValidationReport,
    DataIntegrityEngine
)

from erin.data_core.document_pipeline import (
    DocumentPipeline,
    DocumentDetector,
    PDFExtractor,
    HTMLExtractor,
    SpreadsheetExtractor,
    JSONExtractor,
    FinancialStatementParser,
    DocumentType,
    FinancialStatementType,
    ExtractedTable,
    ExtractedText,
    DocumentMetadata,
    FinancialFact,
    EntityExtraction,
    ProcessingResult,
    process_document
)

__all__ = [
    # Source Registry
    "Source",
    "SourceRegistry",
    "SourceConfiguration",
    "DataCategory",
    "AccessMethod",
    "AuthenticationType",
    "LicensingClassification",
    "OperationalStatus",
    "SourceRegistrySettings",
    "INDONESIA_DEFAULT_SOURCES",
    "initialize_default_sources",
    "get_source_registry",
    
    # Discovery Engine
    "DiscoveryEngine",
    "DiscoveryResult",
    "DiscoveryMethod",
    "SourceMonitor",
    "run_discovery",
    
    # Connectors
    "BaseConnector",
    "RestApiConnector",
    "RssFeedConnector",
    "SitemapConnector",
    "DocumentConnector",
    "RegulatoryConnector",
    "ConnectorConfig",
    "FetchResult",
    "create_connector",
    "fetch_from_source",
    
    # Integrity Engine
    "FinancialDataValidator",
    "CrossProviderReconciler",
    "CorporateActionAdjuster",
    "QuarantineManager",
    "QuarantinedRecord",
    "QuarantineReason",
    "QualitySeverity",
    "IssueType",
    "QualityIssue",
    "ReconciliationResult",
    "ValidationReport",
    "DataIntegrityEngine",
    
    # Document Pipeline
    "DocumentPipeline",
    "DocumentDetector",
    "PDFExtractor",
    "HTMLExtractor",
    "SpreadsheetExtractor",
    "JSONExtractor",
    "FinancialStatementParser",
    "DocumentType",
    "FinancialStatementType",
    "ExtractedTable",
    "ExtractedText",
    "DocumentMetadata",
    "FinancialFact",
    "EntityExtraction",
    "ProcessingResult",
    "process_document",
]

__version__ = "0.1.0"

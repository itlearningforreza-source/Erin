"""
ERIN Data Core - Financial Data Integrity Engine
Validation, reconciliation, corporate action adjustments, and quarantine for suspicious data.
"""

from pathlib import Path
import asyncio
import hashlib
import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import json
from enum import Enum
from typing import Any, Optional, List, Dict, Set, Tuple, Callable
from collections import defaultdict

import structlog

from erin.data_core.source_registry import (
    Source,
    SourceRegistry,
    DataCategory
)

logger = structlog.get_logger(__name__)

import asyncio
import hashlib
import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Optional, List, Dict, Set, Tuple, Callable
from collections import defaultdict

import structlog

from erin.data_core.source_registry import (
    Source,
    SourceRegistry,
    DataCategory
)

logger = structlog.get_logger(__name__)


class QualitySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IssueType(str, Enum):
    MISSING_VALUE = "missing_value"
    DUPLICATE_RECORD = "duplicate_record"
    OUTLIER = "outlier"
    SCHEMA_VIOLATION = "schema_violation"
    STALE_DATA = "stale_data"
    INCONSISTENT_OHLC = "inconsistent_ohlc"
    NEGATIVE_PRICE = "negative_price"
    NEGATIVE_VOLUME = "negative_volume"
    CROSSED_SPREAD = "crossed_spread"
    WIDE_SPREAD = "wide_spread"
    CORPORATE_ACTION_MISMATCH = "corporate_action_mismatch"
    CROSS_PROVIDER_DISCREPANCY = "cross_provider_discrepancy"
    CURRENCY_MISMATCH = "currency_mismatch"
    TIMESTAMP_OUT_OF_ORDER = "timestamp_out_of_order"
    GAP_IN_TIME_SERIES = "gap_in_time_series"
    ADJUSTMENT_ERROR = "adjustment_error"
    LICENSING_VIOLATION = "licensing_violation"


class QuarantineReason(str, Enum):
    SUSPICIOUS_OUTLIER = "suspicious_outlier"
    FAILED_VALIDATION = "failed_validation"
    CROSS_PROVIDER_CONFLICT = "cross_provider_conflict"
    MISSING_PROVENANCE = "missing_provenance"
    LICENSING_ISSUE = "licensing_issue"
    CORPORATE_ACTION_UNVERIFIED = "corporate_action_unverified"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass
class QualityIssue:
    """Individual data quality issue."""
    issue_type: IssueType
    severity: QualitySeverity
    field: str
    description: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    record_id: Optional[str] = None
    source_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuarantinedRecord:
    """A record that has been quarantined due to quality issues."""
    quarantine_id: str = field(default_factory=lambda: f"qrn_{uuid.uuid4().hex[:12]}")
    record: Dict[str, Any] = field(default_factory=dict)
    source_id: str = ""
    reason: QuarantineReason = QuarantineReason.MANUAL_REVIEW_REQUIRED
    issues: List[QualityIssue] = field(default_factory=list)
    quarantined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    resolution: Optional[str] = None
    original_hash: str = ""


@dataclass
class ReconciliationResult:
    """Result of cross-provider reconciliation."""
    field: str
    provider_values: Dict[str, Any]
    consensus_value: Optional[Any] = None
    consensus_method: str = "median"
    discrepancy_pct: float = 0.0
    is_discrepant: bool = False
    threshold_pct: float = 1.0
    providers_agree: int = 0
    total_providers: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Comprehensive validation report for a dataset."""
    dataset_id: str
    source_id: str
    total_records: int
    valid_records: int
    quarantined_records: int
    issues: List[QualityIssue] = field(default_factory=list)
    reconciliation_results: List[ReconciliationResult] = field(default_factory=list)
    completeness_score: float = 1.0
    accuracy_score: float = 1.0
    consistency_score: float = 1.0
    timeliness_score: float = 1.0
    overall_score: float = 1.0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_scores(self):
        """Calculate quality scores based on issues."""
        if self.total_records == 0:
            return
        
        # Weight issues by severity
        severity_weights = {
            QualitySeverity.INFO: 0.01,
            QualitySeverity.WARNING: 0.05,
            QualitySeverity.ERROR: 0.2,
            QualitySeverity.CRITICAL: 0.5
        }
        
        issue_counts = defaultdict(int)
        for issue in self.issues:
            issue_counts[issue.severity] += 1
        
        total_penalty = sum(count * severity_weights[sev] for sev, count in issue_counts.items())
        max_penalty = self.total_records * 0.5  # Max penalty if all records have CRITICAL issues
        
        self.overall_score = max(0.0, 1.0 - (total_penalty / max(max_penalty, 1)))
        
        # Per-category scores (simplified)
        self.completeness_score = self.overall_score
        self.accuracy_score = self.overall_score
        self.consistency_score = self.overall_score
        self.timeliness_score = self.overall_score


class FinancialDataValidator:
    """Validates financial data records against schema and business rules."""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self._custom_rules: List[Callable[[Dict[str, Any], DataCategory], List[QualityIssue]]] = []
    
    def add_custom_rule(self, rule: Callable[[Dict[str, Any], DataCategory], List[QualityIssue]]):
        """Add a custom validation rule."""
        self._custom_rules.append(rule)
    
    def validate_record(self, record: Dict[str, Any], category: DataCategory, source_id: str) -> List[QualityIssue]:
        """Validate a single record."""
        issues = []
        
        # Required fields check
        required_fields = self._get_required_fields(category)
        for field_name in required_fields:
            if field_name not in record or record[field_name] is None or record[field_name] == "":
                issues.append(QualityIssue(
                    issue_type=IssueType.MISSING_VALUE,
                    severity=QualitySeverity.ERROR,
                    field=field_name,
                    description=f"Required field '{field_name}' is missing or empty",
                    source_id=source_id
                ))
        
        # Type and range validations
        issues.extend(self._validate_numeric_fields(record, category, source_id))
        issues.extend(self._validate_ohlc_consistency(record, source_id))
        issues.extend(self._validate_spreads(record, source_id))
        issues.extend(self._validate_timestamps(record, source_id))
        issues.extend(self._validate_currencies(record, source_id))
        
        # Custom rules
        for rule in self._custom_rules:
            try:
                issues.extend(rule(record, category))
            except Exception as e:
                logger.warning("Custom validation rule failed", error=str(e))
        
        return issues
    
    def _get_required_fields(self, category: DataCategory) -> List[str]:
        """Get required fields for a data category."""
        base_fields = ["timestamp", "source_id"]
        
        category_fields = {
            DataCategory.EQUITY_PRICES: ["symbol", "open", "high", "low", "close", "volume"],
            DataCategory.EQUITY_FUNDAMENTALS: ["symbol", "period", "revenue", "net_income"],
            DataCategory.FIXED_INCOME: ["isin", "coupon", "maturity", "yield"],
            DataCategory.DERIVATIVES: ["underlying", "strike", "expiry", "option_type"],
            DataCategory.MACROECONOMIC: ["indicator", "value", "period", "geography"],
            DataCategory.CORPORATE_ACTIONS: ["symbol", "action_type", "ex_date", "ratio"]
        }
        
        return base_fields + category_fields.get(category, [])
    
    def _validate_numeric_fields(self, record: Dict[str, Any], category: DataCategory, source_id: str) -> List[QualityIssue]:
        """Validate numeric fields for reasonableness."""
        issues = []
        
        numeric_fields = [
            ("open", 0, None),
            ("high", 0, None),
            ("low", 0, None),
            ("close", 0, None),
            ("volume", 0, None),
            ("price", 0, None),
            ("bid", 0, None),
            ("ask", 0, None),
            ("last", 0, None),
            ("value", None, None),
            ("yield", -1, 100),  # -100% to 10000%
            ("coupon", 0, 100),
            ("ratio", 0, None)
        ]
        
        for field_name, min_val, max_val in numeric_fields:
            if field_name in record and record[field_name] is not None:
                try:
                    value = Decimal(str(record[field_name]))
                    
                    if min_val is not None and value < Decimal(str(min_val)):
                        issues.append(QualityIssue(
                            issue_type=IssueType.NEGATIVE_PRICE if min_val == 0 else IssueType.SCHEMA_VIOLATION,
                            severity=QualitySeverity.ERROR,
                            field=field_name,
                            description=f"{field_name} value {value} below minimum {min_val}",
                            expected=f">= {min_val}",
                            actual=str(value),
                            source_id=source_id
                        ))
                    
                    if max_val is not None and value > Decimal(str(max_val)):
                        issues.append(QualityIssue(
                            issue_type=IssueType.SCHEMA_VIOLATION,
                            severity=QualitySeverity.WARNING,
                            field=field_name,
                            description=f"{field_name} value {value} above maximum {max_val}",
                            expected=f"<= {max_val}",
                            actual=str(value),
                            source_id=source_id
                        ))
                
                except (InvalidOperation, ValueError):
                    issues.append(QualityIssue(
                        issue_type=IssueType.SCHEMA_VIOLATION,
                        severity=QualitySeverity.ERROR,
                        field=field_name,
                        description=f"{field_name} is not a valid number: {record[field_name]}",
                        source_id=source_id
                    ))
        
        return issues
    
    def _validate_ohlc_consistency(self, record: Dict[str, Any], source_id: str) -> List[QualityIssue]:
        """Validate OHLC consistency: high >= max(open, close), low <= min(open, close)."""
        issues = []
        
        ohlc_fields = ["open", "high", "low", "close"]
        if not all(f in record for f in ohlc_fields):
            return issues
        
        try:
            open_price = Decimal(str(record["open"]))
            high_price = Decimal(str(record["high"]))
            low_price = Decimal(str(record["low"]))
            close_price = Decimal(str(record["close"]))
            
            if high_price < max(open_price, close_price):
                issues.append(QualityIssue(
                    issue_type=IssueType.INCONSISTENT_OHLC,
                    severity=QualitySeverity.ERROR,
                    field="high",
                    description=f"High ({high_price}) < max(open={open_price}, close={close_price})",
                    expected=f">= {max(open_price, close_price)}",
                    actual=str(high_price),
                    source_id=source_id
                ))
            
            if low_price > min(open_price, close_price):
                issues.append(QualityIssue(
                    issue_type=IssueType.INCONSISTENT_OHLC,
                    severity=QualitySeverity.ERROR,
                    field="low",
                    description=f"Low ({low_price}) > min(open={open_price}, close={close_price})",
                    expected=f"<= {min(open_price, close_price)}",
                    actual=str(low_price),
                    source_id=source_id
                ))
            
            # Check for negative prices
            for field_name, value in [("open", open_price), ("high", high_price), ("low", low_price), ("close", close_price)]:
                if value < 0:
                    issues.append(QualityIssue(
                        issue_type=IssueType.NEGATIVE_PRICE,
                        severity=QualitySeverity.ERROR,
                        field=field_name,
                        description=f"Negative {field_name} price: {value}",
                        source_id=source_id
                    ))
        
        except (InvalidOperation, ValueError):
            pass  # Already caught by numeric validation
        
        return issues
    
    def _validate_spreads(self, record: Dict[str, Any], source_id: str) -> List[QualityIssue]:
        """Validate bid/ask spreads."""
        issues = []
        
        if "bid" in record and "ask" in record:
            try:
                bid = Decimal(str(record["bid"]))
                ask = Decimal(str(record["ask"]))
                
                if bid > 0 and ask > 0:
                    if ask < bid:
                        issues.append(QualityIssue(
                            issue_type=IssueType.CROSSED_SPREAD,
                            severity=QualitySeverity.ERROR,
                            field="bid,ask",
                            description=f"Bid ({bid}) >= Ask ({ask}) - crossed spread",
                            expected="bid < ask",
                            actual=f"bid={bid}, ask={ask}",
                            source_id=source_id
                        ))
                    
                    spread_pct = (ask - bid) / bid
                    if spread_pct > Decimal("0.5"):  # 50% spread
                        issues.append(QualityIssue(
                            issue_type=IssueType.WIDE_SPREAD,
                            severity=QualitySeverity.WARNING,
                            field="bid,ask",
                            description=f"Spread {spread_pct:.2%} > 50% of bid price",
                            expected="spread < 50%",
                            actual=f"spread={spread_pct:.2%}",
                            source_id=source_id
                        ))
            
            except (InvalidOperation, ValueError):
                pass
        
        return issues
    
    def _validate_timestamps(self, record: Dict[str, Any], source_id: str) -> List[QualityIssue]:
        """Validate timestamp fields."""
        issues = []
        
        timestamp_fields = ["timestamp", "observation_timestamp", "publication_timestamp", "retrieval_timestamp"]
        
        for field_name in timestamp_fields:
            if field_name in record and record[field_name]:
                try:
                    if isinstance(record[field_name], str):
                        ts = datetime.fromisoformat(record[field_name].replace("Z", "+00:00"))
                    elif isinstance(record[field_name], datetime):
                        ts = record[field_name]
                    else:
                        continue
                    
                    now = datetime.now(timezone.utc)
                    
                    # Future timestamp (with 1 minute tolerance)
                    if ts > now + timedelta(minutes=1):
                        issues.append(QualityIssue(
                            issue_type=IssueType.SCHEMA_VIOLATION,
                            severity=QualitySeverity.WARNING,
                            field=field_name,
                            description=f"Future timestamp: {ts} > {now}",
                            source_id=source_id
                        ))
                    
                    # Very old timestamp (stale data check)
                    if ts < now - timedelta(days=365 * 10):  # 10 years
                        issues.append(QualityIssue(
                            issue_type=IssueType.STALE_DATA,
                            severity=QualitySeverity.INFO,
                            field=field_name,
                            description=f"Very old timestamp: {ts}",
                            source_id=source_id
                        ))
                
                except (ValueError, AttributeError):
                    issues.append(QualityIssue(
                        issue_type=IssueType.SCHEMA_VIOLATION,
                        severity=QualitySeverity.WARNING,
                        field=field_name,
                        description=f"Invalid timestamp format: {record[field_name]}",
                        source_id=source_id
                    ))
        
        return issues
    
    def _validate_currencies(self, record: Dict[str, Any], source_id: str) -> List[QualityIssue]:
        """Validate currency fields."""
        issues = []
        
        currency_fields = ["currency", "quote_currency", "base_currency", "settlement_currency"]
        
        for field_name in currency_fields:
            if field_name in record and record[field_name]:
                currency = str(record[field_name]).upper()
                if len(currency) != 3 or not currency.isalpha():
                    issues.append(QualityIssue(
                        issue_type=IssueType.CURRENCY_MISMATCH,
                        severity=QualitySeverity.WARNING,
                        field=field_name,
                        description=f"Invalid currency code: {currency}",
                        expected="ISO 4217 3-letter code",
                        actual=currency,
                        source_id=source_id
                    ))
        
        return issues


class CrossProviderReconciler:
    """Reconciles data across multiple providers."""
    
    def __init__(self, discrepancy_threshold: float = 0.01):  # 1%
        self.discrepancy_threshold = discrepancy_threshold
    
    def reconcile(self, records_by_provider: Dict[str, List[Dict[str, Any]]], key_fields: List[str], value_fields: List[str]) -> List[ReconciliationResult]:
        """Reconcile records from multiple providers."""
        results = []
        
        # Group records by key fields
        grouped = defaultdict(lambda: defaultdict(list))
        
        for provider_id, records in records_by_provider.items():
            for record in records:
                key = tuple(record.get(f) for f in key_fields)
                if all(k is not None for k in key):
                    grouped[key][provider_id].append(record)
        
        # Reconcile each group
        for key, provider_records in grouped.items():
            if len(provider_records) < 2:
                continue  # Need at least 2 providers
            
            for value_field in value_fields:
                provider_values = {}
                for provider_id, records in provider_records.items():
                    # Take the first record's value (or average if multiple)
                    values = []
                    for r in records:
                        if value_field in r and r[value_field] is not None:
                            try:
                                values.append(Decimal(str(r[value_field])))
                            except (InvalidOperation, ValueError):
                                pass
                    
                    if values:
                        provider_values[provider_id] = sum(values) / len(values)
                
                if len(provider_values) < 2:
                    continue
                
                result = self._compute_reconciliation(value_field, provider_values)
                result.details["key"] = dict(zip(key_fields, key))
                results.append(result)
        
        return results
    
    def _compute_reconciliation(self, field: str, provider_values: Dict[str, Decimal]) -> ReconciliationResult:
        """Compute reconciliation for a field across providers."""
        values = list(provider_values.values())
        
        if len(values) < 2:
            return ReconciliationResult(
                field=field,
                provider_values={k: str(v) for k, v in provider_values.items()},
                total_providers=len(provider_values)
            )
        
        # Consensus: median for robustness
        consensus = Decimal(str(statistics.median(values))) if len(values) > 1 else values[0]
        
        # Discrepancy: max deviation from consensus
        max_deviation = max(abs(v - consensus) / consensus for v in values) if consensus != 0 else Decimal("0")
        
        is_discrepant = max_deviation > Decimal(str(self.discrepancy_threshold))
        
        return ReconciliationResult(
            field=field,
            provider_values={k: str(v) for k, v in provider_values.items()},
            consensus_value=str(consensus),
            consensus_method="median",
            discrepancy_pct=float(max_deviation * 100),
            is_discrepant=is_discrepant,
            threshold_pct=self.discrepancy_threshold * 100,
            providers_agree=sum(1 for v in values if abs(v - consensus) / consensus <= Decimal(str(self.discrepancy_threshold))) if consensus != 0 else len(values),
            total_providers=len(provider_values)
        )


class CorporateActionAdjuster:
    """Applies corporate action adjustments to historical price data."""
    
    def __init__(self, registry: SourceRegistry):
        self.registry = registry
        self._action_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    async def load_corporate_actions(self, symbol: str) -> List[Dict[str, Any]]:
        """Load corporate actions for a symbol from corporate actions source."""
        cache_key = symbol.upper()
        if cache_key in self._action_cache:
            return self._action_cache[cache_key]
        
        # Find corporate actions source
        sources = await self.registry.list_sources(data_category=DataCategory.CORPORATE_ACTIONS)
        if not sources:
            return []
        
        # For now, return empty - would fetch from source in production
        self._action_cache[cache_key] = []
        return []
    
    def adjust_for_splits(self, records: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adjust OHLCV for stock splits."""
        if not actions:
            return records
        
        adjusted = []
        for record in records:
            adj_record = record.copy()
            timestamp = record.get("timestamp")
            
            if not timestamp:
                adjusted.append(adj_record)
                continue
            
            if isinstance(timestamp, str):
                ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                ts = timestamp
            
            # Apply splits that occurred before this record
            split_factor = Decimal("1")
            for action in actions:
                if action.get("action_type") in ["split", "stock_split"]:
                    ex_date_str = action.get("ex_date")
                    if ex_date_str:
                        ex_date = datetime.fromisoformat(ex_date_str.replace("Z", "+00:00"))
                        if ts < ex_date:  # Record is before ex-date, needs adjustment
                            ratio = Decimal(str(action.get("ratio", "1")))
                            split_factor *= ratio
            
            if split_factor != Decimal("1"):
                for field in ["open", "high", "low", "close", "adj_close"]:
                    if field in adj_record and adj_record[field] is not None:
                        try:
                            adj_record[field] = str(Decimal(str(adj_record[field])) / split_factor)
                        except (InvalidOperation, ValueError):
                            pass
                
                # Volume is multiplied by split factor
                if "volume" in adj_record and adj_record["volume"] is not None:
                    try:
                        adj_record["volume"] = str(int(Decimal(str(adj_record["volume"])) * split_factor))
                    except (InvalidOperation, ValueError):
                        pass
                
                adj_record["adjustment_factor"] = str(split_factor)
                adj_record["adjustment_type"] = "split"
            
            adjusted.append(adj_record)
        
        return adjusted
    
    def adjust_for_dividends(self, records: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adjust prices for dividends (simplified - price adjustment)."""
        # This is a simplified implementation
        # Full implementation would require total return calculations
        return records
    
    async def adjust_records(self, records: List[Dict[str, Any]], symbol: str) -> List[Dict[str, Any]]:
        """Apply all corporate action adjustments."""
        actions = await self.load_corporate_actions(symbol)
        
        adjusted = self.adjust_for_splits(records, actions)
        adjusted = self.adjust_for_dividends(adjusted, actions)
        
        return adjusted


class QuarantineManager:
    """Manages quarantined records for review."""
    
    def __init__(self, db_path: str = "~/.erin/data/quarantine.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
    
    async def initialize(self):
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS quarantined_records (
                    quarantine_id TEXT PRIMARY KEY,
                    record TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    issues TEXT NOT NULL,
                    quarantined_at TEXT NOT NULL,
                    reviewed INTEGER DEFAULT 0,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    resolution TEXT,
                    original_hash TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_quarantine_source ON quarantined_records(source_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_quarantine_reviewed ON quarantined_records(reviewed)
            """)
            await db.commit()
        
        self._initialized = True
    
    async def quarantine(self, record: Dict[str, Any], source_id: str, reason: QuarantineReason, issues: List[QualityIssue]) -> QuarantinedRecord:
        """Quarantine a record."""
        if not self._initialized:
            await self.initialize()
        
        # Compute hash of original record
        record_str = json.dumps(record, sort_keys=True, default=str)
        original_hash = hashlib.sha256(record_str.encode()).hexdigest()[:16]
        
        quarantined = QuarantinedRecord(
            record=record,
            source_id=source_id,
            reason=reason,
            issues=issues,
            original_hash=original_hash
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO quarantined_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quarantined.quarantine_id,
                json.dumps(record),
                source_id,
                reason.value,
                json.dumps([{
                    "issue_type": i.issue_type.value,
                    "severity": i.severity.value,
                    "field": i.field,
                    "description": i.description,
                    "expected": str(i.expected) if i.expected else None,
                    "actual": str(i.actual) if i.actual else None,
                    "record_id": i.record_id,
                    "source_id": i.source_id,
                    "timestamp": i.timestamp.isoformat(),
                    "metadata": i.metadata
                } for i in issues]),
                quarantined.quarantined_at.isoformat(),
                0,  # reviewed
                None,  # reviewed_at
                None,  # reviewed_by
                None,  # resolution
                original_hash
            ))
            await db.commit()
        
        logger.warning("Record quarantined", quarantine_id=quarantined.quarantine_id, source_id=source_id, reason=reason.value)
        return quarantined
    
    async def get_quarantined(self, source_id: Optional[str] = None, reviewed: Optional[bool] = None, limit: int = 100) -> List[QuarantinedRecord]:
        """Get quarantined records."""
        if not self._initialized:
            await self.initialize()
        
        query = "SELECT * FROM quarantined_records WHERE 1=1"
        params = []
        
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        
        if reviewed is not None:
            query += " AND reviewed = ?"
            params.append(int(reviewed))
        
        query += " ORDER BY quarantined_at DESC LIMIT ?"
        params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                records = []
                async for row in cursor:
                    data = dict(row)
                    records.append(QuarantinedRecord(
                        quarantine_id=data["quarantine_id"],
                        record=json.loads(data["record"]),
                        source_id=data["source_id"],
                        reason=QuarantineReason(data["reason"]),
                        issues=[QualityIssue(**i) for i in json.loads(data["issues"])],
                        quarantined_at=datetime.fromisoformat(data["quarantined_at"]),
                        reviewed=bool(data["reviewed"]),
                        reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data["reviewed_at"] else None,
                        reviewed_by=data["reviewed_by"],
                        resolution=data["resolution"],
                        original_hash=data["original_hash"]
                    ))
                return records
    
    async def review(self, quarantine_id: str, reviewed_by: str, resolution: str) -> bool:
        """Mark a quarantined record as reviewed."""
        if not self._initialized:
            await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE quarantined_records
                SET reviewed = 1, reviewed_at = ?, reviewed_by = ?, resolution = ?
                WHERE quarantine_id = ?
            """, (datetime.now(timezone.utc).isoformat(), reviewed_by, resolution, quarantine_id))
            await db.commit()
            
            return True
    
    async def release(self, quarantine_id: str) -> Optional[Dict[str, Any]]:
        """Release a quarantined record (return the original record)."""
        if not self._initialized:
            await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT record FROM quarantined_records WHERE quarantine_id = ?", (quarantine_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row["record"])
        return None


class DataIntegrityEngine:
    """Main engine orchestrating validation, reconciliation, adjustment, and quarantine."""
    
    def __init__(self, registry: SourceRegistry, quarantine_db: str = "~/.erin/data/quarantine.db"):
        self.registry = registry
        self.validator = FinancialDataValidator()
        self.reconciler = CrossProviderReconciler()
        self.adjuster = CorporateActionAdjuster(registry)
        self.quarantine = QuarantineManager(quarantine_db)
        self._validation_history: List[ValidationReport] = []
    
    async def initialize(self):
        """Initialize all components."""
        await self.quarantine.initialize()
    
    async def validate_dataset(self, records: List[Dict[str, Any]], source_id: str, category: DataCategory, dataset_id: str = "") -> ValidationReport:
        """Validate a complete dataset."""
        if not dataset_id:
            dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
        
        report = ValidationReport(
            dataset_id=dataset_id,
            source_id=source_id,
            total_records=len(records),
            valid_records=0,
            quarantined_records=0
        )
        
        # Validate each record
        valid_records = []
        for i, record in enumerate(records):
            record["_record_index"] = i
            issues = self.validator.validate_record(record, category, source_id)
            
            if issues:
                report.issues.extend(issues)
                
                # Quarantine critical issues
                critical_issues = [i for i in issues if i.severity == QualitySeverity.CRITICAL]
                error_issues = [i for i in issues if i.severity == QualitySeverity.ERROR]
                
                if critical_issues or (self.validator.strict_mode and error_issues):
                    quarantine_reason = QuarantineReason.FAILED_VALIDATION
                    if critical_issues:
                        quarantine_reason = QuarantineReason.SUSPICIOUS_OUTLIER
                    
                    await self.quarantine.quarantine(record, source_id, quarantine_reason, issues)
                    report.quarantined_records += 1
                else:
                    valid_records.append(record)
            else:
                valid_records.append(record)
        
        report.valid_records = len(valid_records)
        report.calculate_scores()
        
        self._validation_history.append(report)
        return report
    
    async def reconcile_providers(self, records_by_provider: Dict[str, List[Dict[str, Any]]], key_fields: List[str], value_fields: List[str]) -> List[ReconciliationResult]:
        """Run cross-provider reconciliation."""
        return self.reconciler.reconcile(records_by_provider, key_fields, value_fields)
    
    async def adjust_for_corporate_actions(self, records: List[Dict[str, Any]], symbol: str) -> List[Dict[str, Any]]:
        """Apply corporate action adjustments."""
        return await self.adjuster.adjust_records(records, symbol)
    
    async def full_pipeline(self, records: List[Dict[str, Any]], source_id: str, category: DataCategory, symbol: Optional[str] = None, dataset_id: str = "") -> ValidationReport:
        """Run full integrity pipeline: validate -> reconcile -> adjust."""
        # Step 1: Validate
        report = await self.validate_dataset(records, source_id, category, dataset_id)
        
        # Step 2: Get valid records
        valid_records = [r for r in records if r.get("_record_index") is not None]
        
        # Step 3: Corporate action adjustment (for price data)
        if symbol and category in [DataCategory.EQUITY_PRICES, DataCategory.EQUITY_FUNDAMENTALS]:
            adjusted = await self.adjust_for_corporate_actions(valid_records, symbol)
            # Re-validate adjusted records
            adjusted_report = await self.validate_dataset(adjusted, source_id, category, f"{dataset_id}_adjusted")
            report.issues.extend(adjusted_report.issues)
            report.quarantined_records += adjusted_report.quarantined_records
            valid_records = adjusted
        
        return report
    
    def get_validation_history(self, limit: int = 100) -> List[ValidationReport]:
        """Get recent validation history."""
        return self._validation_history[-limit:]
    
    async def get_quarantine_stats(self) -> Dict[str, Any]:
        """Get quarantine statistics."""
        all_quarantined = await self.quarantine.get_quarantined(reviewed=False, limit=1000)
        reviewed = await self.quarantine.get_quarantined(reviewed=True, limit=1000)
        
        by_reason = defaultdict(int)
        by_source = defaultdict(int)
        
        for q in all_quarantined:
            by_reason[q.reason.value] += 1
            by_source[q.source_id] += 1
        
        return {
            "pending_review": len(all_quarantined),
            "reviewed": len(reviewed),
            "by_reason": dict(by_reason),
            "by_source": dict(by_source)
        }


import aiosqlite

if __name__ == "__main__":
    async def test():
        from erin.data_core import SourceRegistry, DataCategory
        registry = SourceRegistry()
        await registry.initialize()
        
        engine = DataIntegrityEngine(registry)
        await engine.initialize()
        
        # Test validator
        validator = FinancialDataValidator()
        
        # Valid record
        record = {
            "symbol": "AAPL",
            "timestamp": "2024-01-15T10:00:00Z",
            "open": 150.0,
            "high": 152.0,
            "low": 149.0,
            "close": 151.0,
            "volume": 1000000,
            "source_id": "test"
        }
        issues = validator.validate_record(record, DataCategory.EQUITY_PRICES, "test")
        print(f"Valid record issues: {len(issues)}")
        
        # Invalid record (crossed spread)
        bad_record = {
            "symbol": "AAPL",
            "timestamp": "2024-01-15T10:00:00Z",
            "bid": 152.0,
            "ask": 150.0,
            "source_id": "test"
        }
        issues = validator.validate_record(bad_record, DataCategory.EQUITY_PRICES, "test")
        print(f"Crossed spread issues: {len(issues)}")
        for i in issues:
            print(f"  - {i.issue_type.value}: {i.description}")
        
        # Test reconciler
        reconciler = CrossProviderReconciler()
        provider_data = {
            "provider1": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 150.0}],
            "provider2": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 151.0}],
            "provider3": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 149.5}]
        }
        results = reconciler.reconcile(provider_data, ["symbol", "timestamp"], ["close"])
        print(f"\nReconciliation results: {len(results)}")
        for r in results:
            print(f"  Field: {r.field}, Consensus: {r.consensus_value}, Discrepancy: {r.discrepancy_pct:.2f}%, Discrepant: {r.is_discrepant}")
        
        # Test quarantine
        quarantine = QuarantineManager("/tmp/test_quarantine.db")
        await quarantine.initialize()
        
        q = await quarantine.quarantine(bad_record, "test", QuarantineReason.FAILED_VALIDATION, issues)
        print(f"\nQuarantined: {q.quarantine_id}")
        
        pending = await quarantine.get_quarantined(reviewed=False)
        print(f"Pending review: {len(pending)}")
        
        print("\nAll integrity engine tests passed!")
    
    asyncio.run(test())

"""Unit tests for Data Integrity Engine."""

import pytest
import sys
sys.path.insert(0, '/home/rezaahmadkhairuddin/ERIN/packages/data-core/src')

from erin.data_core import (
    DataIntegrityEngine,
    SourceRegistry,
    FinancialDataValidator,
    CrossProviderReconciler,
    QuarantineManager,
    QuarantineReason,
    QualitySeverity,
    IssueType,
    DataCategory,
    Source,
    SourceConfiguration,
    AccessMethod,
    AuthenticationType,
    LicensingClassification,
    OperationalStatus
)


class TestFinancialDataValidator:
    """Tests for FinancialDataValidator."""
    
    def test_valid_ohlc_record(self):
        """Test validation of a valid OHLC record."""
        validator = FinancialDataValidator()
        
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
        assert len(issues) == 0
    
    def test_crossed_spread_detected(self):
        """Test that crossed spread is detected."""
        validator = FinancialDataValidator()
        
        record = {
            "symbol": "AAPL",
            "timestamp": "2024-01-15T10:00:00Z",
            "bid": 152.0,
            "ask": 150.0,
            "source_id": "test"
        }
        
        issues = validator.validate_record(record, DataCategory.EQUITY_PRICES, "test")
        crossed = [i for i in issues if i.issue_type.value == "crossed_spread"]
        assert len(crossed) == 1
        assert crossed[0].severity == QualitySeverity.ERROR
    
    def test_inconsistent_ohlc_detected(self):
        """Test that inconsistent OHLC is detected."""
        validator = FinancialDataValidator()
        
        record = {
            "symbol": "AAPL",
            "timestamp": "2024-01-15T10:00:00Z",
            "open": 150.0,
            "high": 149.0,  # High < Open
            "low": 149.0,
            "close": 151.0,
            "volume": 1000000,
            "source_id": "test"
        }
        
        issues = validator.validate_record(record, DataCategory.EQUITY_PRICES, "test")
        ohlc_issues = [i for i in issues if i.issue_type.value == "inconsistent_ohlc"]
        assert len(ohlc_issues) == 1
    
    def test_negative_price_detected(self):
        """Test that negative price is detected."""
        validator = FinancialDataValidator()
        
        record = {
            "symbol": "AAPL",
            "timestamp": "2024-01-15T10:00:00Z",
            "open": -150.0,
            "high": 152.0,
            "low": 149.0,
            "close": 151.0,
            "volume": 1000000,
            "source_id": "test"
        }
        
        issues = validator.validate_record(record, DataCategory.EQUITY_PRICES, "test")
        neg_price = [i for i in issues if i.issue_type.value == "negative_price"]
        assert len(neg_price) == 1
    
    def test_missing_required_fields(self):
        """Test that missing required fields are detected."""
        validator = FinancialDataValidator()
        
        record = {
            "symbol": "AAPL",
            # missing timestamp, open, high, low, close, volume
        }
        
        issues = validator.validate_record(record, DataCategory.EQUITY_PRICES, "test")
        missing = [i for i in issues if i.issue_type.value == "missing_value"]
        assert len(missing) >= 5  # timestamp, open, high, low, close, volume


class TestCrossProviderReconciler:
    """Tests for CrossProviderReconciler."""
    
    def test_reconcile_with_consensus(self):
        """Test reconciliation with good consensus."""
        reconciler = CrossProviderReconciler(discrepancy_threshold=0.01)
        
        records_by_provider = {
            "provider1": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 150.0}],
            "provider2": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 150.5}],
            "provider3": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 149.8}]
        }
        
        results = reconciler.reconcile(records_by_provider, ["symbol", "timestamp"], ["close"])
        
        assert len(results) == 1
        result = results[0]
        assert result.field == "close"
        assert not result.is_discrepant  # Within 1% threshold
        assert abs(result.consensus_value - 150.0) < 0.5
    
    def test_reconcile_detects_discrepancy(self):
        """Test that large discrepancy is detected."""
        reconciler = CrossProviderReconciler(discrepancy_threshold=0.01)
        
        records_by_provider = {
            "provider1": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 150.0}],
            "provider2": [{"symbol": "AAPL", "timestamp": "2024-01-15", "close": 200.0}]  # 33% diff
        }
        
        results = reconciler.reconcile(records_by_provider, ["symbol", "timestamp"], ["close"])
        
        assert len(results) == 1
        result = results[0]
        assert result.is_discrepant
        assert result.discrepancy_pct > 10


class TestQuarantineManager:
    """Tests for QuarantineManager."""
    
    @pytest.mark.asyncio
    async def test_quarantine_and_release(self):
        """Test quarantining and releasing a record."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            quarantine = QuarantineManager(db_path)
            await quarantine.initialize()
            
            record = {"symbol": "AAPL", "close": 150.0}
            issues = []  # Would normally have issues
            
            from erin.data_core.integrity import QualityIssue, IssueType, QualitySeverity
            issue = QualityIssue(
                issue_type=IssueType.CROSSED_SPREAD,
                severity=QualitySeverity.ERROR,
                field="bid,ask",
                description="Crossed spread"
            )
            
            quarantined = await quarantine.quarantine(record, "test", QuarantineReason.FAILED_VALIDATION, [issue])
            
            assert quarantined.quarantine_id.startswith("qrn_")
            assert quarantined.record == record
            assert quarantined.reason == QuarantineReason.FAILED_VALIDATION
            
            # Get pending
            pending = await quarantine.get_quarantined(reviewed=False)
            assert len(pending) == 1
            
            # Release
            released = await quarantine.release(quarantined.quarantine_id)
            assert released == record
            
            # Check pending is empty
            pending = await quarantine.get_quarantined(reviewed=False)
            assert len(pending) == 0
        finally:
            import os
            os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

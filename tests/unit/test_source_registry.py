"""Unit tests for Source Registry."""

import asyncio
import tempfile
import pytest
import sys
sys.path.insert(0, '/home/rezaahmadkhairuddin/ERIN/packages/data-core/src')

from erin.data_core import SourceRegistry, Source, DataCategory, AccessMethod, AuthenticationType, LicensingClassification, OperationalStatus, SourceConfiguration


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    import os
    os.unlink(db_path)


@pytest.fixture
async def registry(temp_db):
    """Create a registry with temporary database."""
    reg = SourceRegistry()
    reg.db_path = temp_db
    await reg.initialize()
    yield reg


class TestSourceRegistry:
    """Tests for SourceRegistry."""
    
    @pytest.mark.asyncio
    async def test_register_source(self, registry):
        """Test registering a new source."""
        source = Source(
            name="Test Source",
            domain="test.example.com",
            data_category=DataCategory.MACROECONOMIC,
            access_method=AccessMethod.REST_API,
            authentication=AuthenticationType.API_KEY,
            licensing=LicensingClassification.OPEN_DATA,
            config=SourceConfiguration(
                base_url="https://api.test.example.com",
                rate_limit_rpm=60
            )
        )
        
        registered = await registry.register(source)
        assert registered.source_id.startswith("src_")
        assert registered.name == "Test Source"
        assert registered.domain == "test.example.com"
    
    @pytest.mark.asyncio
    async def test_duplicate_source_rejected(self, registry):
        """Test that duplicate domain+name is rejected."""
        source = Source(
            name="Test Source",
            domain="test.example.com",
            data_category=DataCategory.MACROECONOMIC,
            access_method=AccessMethod.REST_API,
        )
        await registry.register(source)
        
        with pytest.raises(ValueError, match="already exists"):
            await registry.register(source)
    
    @pytest.mark.asyncio
    async def test_get_source(self, registry):
        """Test getting a source by ID."""
        source = Source(
            name="Test Source",
            domain="test.example.com",
            data_category=DataCategory.MACROECONOMIC,
            access_method=AccessMethod.REST_API,
        )
        registered = await registry.register(source)
        
        retrieved = await registry.get(registered.source_id)
        assert retrieved is not None
        assert retrieved.source_id == registered.source_id
    
    @pytest.mark.asyncio
    async def test_list_sources_with_filters(self, registry):
        """Test listing sources with filters."""
        # Register multiple sources
        for i in range(3):
            source = Source(
                name=f"Source {i}",
                domain=f"source{i}.example.com",
                data_category=DataCategory.MACROECONOMIC,
                access_method=AccessMethod.REST_API,
                reliability_score=0.5 + i * 0.1
            )
            await registry.register(source)
        
        # Filter by category
        macro = await registry.list_sources(data_category=DataCategory.MACROECONOMIC)
        assert len(macro) >= 3
        
        # Filter by min reliability
        high_rel = await registry.list_sources(min_reliability=0.7)
        assert len(high_rel) >= 1
        
        # Sort by reliability (descending)
        sources = await registry.list_sources()
        reliabilities = [s.reliability_score for s in sources]
        assert reliabilities == sorted(reliabilities, reverse=True)
    
    @pytest.mark.asyncio
    async def test_record_fetch_result(self, registry):
        """Test recording fetch results."""
        source = Source(
            name="Test Source",
            domain="test.example.com",
            data_category=DataCategory.MACROECONOMIC,
            access_method=AccessMethod.REST_API,
        )
        registered = await registry.register(source)
        
        # Record success
        await registry.record_fetch_result(registered.source_id, True, 150.0)
        
        updated = await registry.get(registered.source_id)
        assert updated.total_fetches == 1
        assert updated.successful_fetches == 1
        assert updated.consecutive_failures == 0
        assert updated.avg_latency_ms == 150.0
    
    @pytest.mark.asyncio
    async def test_verify_source(self, registry):
        """Test source verification."""
        source = Source(
            name="Test Source",
            domain="test.example.com",
            data_category=DataCategory.MACROECONOMIC,
            access_method=AccessMethod.REST_API,
            verified=False
        )
        registered = await registry.register(source)
        
        result = await registry.verify_source(registered.source_id, "tester", "Verified manually")
        assert result is True
        
        verified = await registry.get(registered.source_id)
        assert verified.verified is True
        assert verified.verified_by == "tester"
        assert verified.operational_status == OperationalStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_get_stats(self, registry):
        """Test getting registry statistics."""
        stats = await registry.get_stats()
        assert "total_sources" in stats
        assert "verified_sources" in stats
        assert "average_reliability" in stats
        assert "by_category" in stats
        assert "by_status" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

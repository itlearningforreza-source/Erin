"""
ERIN AI Intelligence - Acquisition Agent
Autonomously acquires data from registered sources.
"""

import asyncio
from typing import Any, Dict, List, Optional

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.data_core import SourceRegistry, fetch_from_source, Source, DataCategory


class AcquisitionAgentConfig(AgentConfig):
    """Configuration for Acquisition Agent."""
    agent_type: str = "acquisition"
    name: str = "Acquisition Agent"
    description: str = "Autonomously acquires data from registered sources"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.ACCESS_EXTERNAL_API,
        AgentPermission.READ_MARKET_DATA,
        AgentPermission.WRITE_MARKET_DATA,
        AgentPermission.RUN_COMPUTATIONS,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["fetch_sensitive_data"])


class AcquisitionAgent(BaseAgent):
    """Agent that acquires data from registered sources."""
    
    def __init__(self, config: AcquisitionAgentConfig, task_queue: asyncio.Queue, registry: SourceRegistry, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.registry = registry
        self._max_concurrent_fetches = config.resource_limits.get("max_concurrent_fetches", 3)
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute acquisition tasks."""
        action = task.action
        
        if action == "fetch_from_source":
            return await self._fetch_from_source(task.payload)
        elif action == "fetch_category":
            return await self._fetch_category(task.payload)
        elif action == "fetch_all_active":
            return await self._fetch_all_active(task.payload)
        elif action == "get_fetch_stats":
            return await self._get_fetch_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _fetch_from_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch data from a specific source."""
        source_id = payload.get("source_id")
        if not source_id:
            raise ValueError("source_id required")
        
        source = await self.registry.get(source_id)
        if not source:
            raise ValueError(f"Source not found: {source_id}")
        
        # Fetch data
        result = await fetch_from_source(source, self.registry)
        
        return {
            "source_id": source_id,
            "source_name": source.name,
            "success": result.success,
            "records_count": result.records_count,
            "latency_ms": result.latency_ms,
            "error": result.error,
            "watermark": result.watermark
        }
    
    async def _fetch_category(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch data from all sources in a category."""
        category_str = payload.get("category")
        if not category_str:
            raise ValueError("category required")
        
        category = DataCategory(category_str)
        sources = await self.registry.get_by_category(category)
        
        # Filter active sources
        active_sources = [s for s in sources if s.operational_status.value == "active"]
        
        # Limit concurrent fetches
        semaphore = asyncio.Semaphore(self._max_concurrent_fetches)
        
        async def fetch_with_semaphore(source: Source):
            async with semaphore:
                return await fetch_from_source(source, self.registry)
        
        tasks = [fetch_with_semaphore(s) for s in active_sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = 0
        failed = 0
        total_records = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
            elif result.success:
                successful += 1
                total_records += result.records_count
            else:
                failed += 1
        
        return {
            "category": category_str,
            "total_sources": len(active_sources),
            "successful": successful,
            "failed": failed,
            "total_records": total_records
        }
    
    async def _fetch_all_active(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch from all active sources across categories."""
        categories = list(DataCategory)
        
        results = {}
        for category in categories:
            sources = await self.registry.get_by_category(category)
            active = [s for s in sources if s.operational_status.value == "active"]
            if active:
                cat_result = await self._fetch_category({"category": category.value})
                results[category.value] = cat_result
        
        total_successful = sum(r.get("successful", 0) for r in results.values())
        total_failed = sum(r.get("failed", 0) for r in results.values())
        total_records = sum(r.get("total_records", 0) for r in results.values())
        
        return {
            "categories": results,
            "summary": {
                "successful": total_successful,
                "failed": total_failed,
                "total_records": total_records
            }
        }
    
    async def _get_fetch_stats(self) -> Dict[str, Any]:
        """Get fetch statistics from registry."""
        stats = await self.registry.get_stats()
        
        return {
            "registry": stats,
            "max_concurrent_fetches": self._max_concurrent_fetches
        }


if __name__ == "__main__":
    # Test
    import asyncio
    from erin.data_core import SourceRegistry
    
    async def test():
        registry = SourceRegistry()
        await registry.initialize()
        
        queue = asyncio.Queue()
        config = AcquisitionAgentConfig(agent_id="acquisition_001")
        
        agent = AcquisitionAgent(config, queue, registry)
        await agent.start()
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Acquisition agent test passed!")
    
    asyncio.run(test())

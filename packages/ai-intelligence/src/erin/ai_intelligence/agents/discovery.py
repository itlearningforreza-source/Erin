"""
ERIN AI Intelligence - Discovery Agent
Autonomously discovers new financial data sources.
"""

import asyncio
from typing import Any, Dict, List, Optional

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.data_core import DiscoveryEngine, SourceRegistry, run_discovery, DataCategory


class DiscoveryAgentConfig(AgentConfig):
    """Configuration for Discovery Agent."""
    agent_type: str = "discovery"
    name: str = "Discovery Agent"
    description: str = "Autonomously discovers new financial data sources"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.ACCESS_EXTERNAL_API,
        AgentPermission.RUN_COMPUTATIONS,
        AgentPermission.ACCESS_KNOWLEDGE_BASE,
        AgentPermission.MODIFY_KNOWLEDGE_BASE,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["register_source"])


class DiscoveryAgent(BaseAgent):
    """Agent that discovers new financial data sources."""
    
    def __init__(self, config: DiscoveryAgentConfig, task_queue: asyncio.Queue, registry: SourceRegistry, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.registry = registry
        self.discovery_engine = DiscoveryEngine(registry)
        self._auto_discovery_enabled = True
        self._discovery_interval_hours = 24
        self._min_confidence_auto_register = 0.7
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute discovery tasks."""
        action = task.action
        
        if action == "run_discovery_cycle":
            return await self._run_discovery_cycle(task.payload)
        elif action == "discover_from_rss":
            return await self._discover_from_rss(task.payload)
        elif action == "discover_from_sitemap":
            return await self._discover_from_sitemap(task.payload)
        elif action == "discover_regulatory":
            return await self._discover_regulatory(task.payload)
        elif action == "auto_register_sources":
            return await self._auto_register_sources(task.payload)
        elif action == "get_discovery_stats":
            return await self._get_discovery_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _run_discovery_cycle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a full discovery cycle."""
        seed_urls = payload.get("seed_urls")
        
        async with self.discovery_engine as engine:
            results = await engine.run_discovery_cycle(seed_urls)
            
            # Auto-register high-confidence sources
            registered = await engine.auto_register_high_confidence(results, self._min_confidence_auto_register)
            
            return {
                "discovered": len(results),
                "auto_registered": registered,
                "results": [
                    {
                        "source_name": r.source.name,
                        "domain": r.source.domain,
                        "confidence": r.confidence,
                        "method": r.discovery_method,
                        "evidence": r.evidence[:3]  # First 3 evidence items
                    }
                    for r in results
                ]
            }
    
    async def _discover_from_rss(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Discover sources from RSS feed."""
        feed_url = payload.get("feed_url")
        if not feed_url:
            raise ValueError("feed_url required")
        
        async with self.discovery_engine as engine:
            results = await engine.discover_from_rss(feed_url)
            return {
                "discovered": len(results),
                "results": [r.source.name for r in results]
            }
    
    async def _discover_from_sitemap(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Discover sources from sitemap."""
        sitemap_url = payload.get("sitemap_url")
        if not sitemap_url:
            raise ValueError("sitemap_url required")
        
        async with self.discovery_engine as engine:
            results = await engine.discover_from_sitemap(sitemap_url)
            return {
                "discovered": len(results),
                "results": [r.source.name for r in results]
            }
    
    async def _discover_regulatory(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Discover sources from regulatory website."""
        base_url = payload.get("base_url")
        if not base_url:
            raise ValueError("base_url required")
        
        async with self.discovery_engine as engine:
            results = await engine.discover_regulatory_sources(base_url)
            return {
                "discovered": len(results),
                "results": [r.source.name for r in results]
            }
    
    async def _auto_register_sources(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-register high-confidence discovered sources."""
        min_confidence = payload.get("min_confidence", self._min_confidence_auto_register)
        
        # Run discovery first
        async with self.discovery_engine as engine:
            results = await engine.run_discovery_cycle()
            registered = await engine.auto_register_high_confidence(results, min_confidence)
            
            return {
                "registered": registered,
                "total_discovered": len(results)
            }
    
    async def _get_discovery_stats(self) -> Dict[str, Any]:
        """Get discovery statistics."""
        registry_stats = await self.registry.get_stats()
        
        return {
            "registry": registry_stats,
            "auto_discovery_enabled": self._auto_discovery_enabled,
            "discovery_interval_hours": self._discovery_interval_hours,
            "min_confidence_auto_register": self._min_confidence_auto_register
        }


if __name__ == "__main__":
    # Test
    import asyncio
    from erin.data_core import SourceRegistry
    
    async def test():
        registry = SourceRegistry()
        await registry.initialize()
        
        queue = asyncio.Queue()
        config = DiscoveryAgentConfig(agent_id="discovery_001")
        
        agent = DiscoveryAgent(config, queue, registry)
        await agent.start()
        
        # Test discovery cycle
        task = AgentTask(
            agent_type="discovery",
            action="run_discovery_cycle",
            payload={},
            priority=TaskPriority.NORMAL
        )
        await queue.put(task)
        
        await asyncio.sleep(2)
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Discovery agent test passed!")
    
    asyncio.run(test())

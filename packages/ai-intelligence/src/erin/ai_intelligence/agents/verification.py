"""
ERIN AI Intelligence - Verification Agent
Validates data quality and integrity.
"""

import asyncio
from typing import Any, Dict, List, Optional

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.data_core import DataIntegrityEngine, SourceRegistry


class VerificationAgentConfig(AgentConfig):
    """Configuration for Verification Agent."""
    agent_type: str = "verification"
    name: str = "Verification Agent"
    description: str = "Validates data quality and integrity"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.READ_MARKET_DATA,
        AgentPermission.READ_FINANCIALS,
        AgentPermission.RUN_COMPUTATIONS,
        AgentPermission.ACCESS_KNOWLEDGE_BASE,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["quarantine_release"])


class VerificationAgent(BaseAgent):
    """Agent that validates data quality and manages quarantine."""
    
    def __init__(self, config: VerificationAgentConfig, task_queue: asyncio.Queue, registry: SourceRegistry, integrity_engine: DataIntegrityEngine, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.registry = registry
        self.integrity_engine = integrity_engine
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute verification tasks."""
        action = task.action
        
        if action == "validate_dataset":
            return await self._validate_dataset(task.payload)
        elif action == "reconcile_providers":
            return await self._reconcile_providers(task.payload)
        elif action == "check_quarantine":
            return await self._check_quarantine(task.payload)
        elif action == "review_quarantined":
            return await self._review_quarantined(task.payload)
        elif action == "get_verification_stats":
            return await self._get_verification_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _validate_dataset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a dataset using the integrity engine."""
        records = payload.get("records", [])
        source_id = payload.get("source_id", "unknown")
        category_str = payload.get("category", "equity_prices")
        dataset_id = payload.get("dataset_id", "")
        
        from erin.data_core import DataCategory
        category = DataCategory(category_str)
        
        report = await self.integrity_engine.validate_dataset(records, source_id, category, dataset_id)
        
        return {
            "dataset_id": report.dataset_id,
            "source_id": report.source_id,
            "total_records": report.total_records,
            "valid_records": report.valid_records,
            "quarantined_records": report.quarantined_records,
            "overall_score": report.overall_score,
            "completeness_score": report.completeness_score,
            "accuracy_score": report.accuracy_score,
            "consistency_score": report.consistency_score,
            "timeliness_score": report.timeliness_score,
            "issues_count": len(report.issues),
            "quarantine_stats": await self.integrity_engine.get_quarantine_stats()
        }
    
    async def _reconcile_providers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run cross-provider reconciliation."""
        records_by_provider = payload.get("records_by_provider", {})
        key_fields = payload.get("key_fields", ["symbol", "timestamp"])
        value_fields = payload.get("value_fields", ["close"])
        
        results = await self.integrity_engine.reconcile_providers(records_by_provider, key_fields, value_fields)
        
        discrepant = [r for r in results if r.is_discrepant]
        
        return {
            "total_fields_checked": len(results),
            "discrepant_fields": len(discrepant),
            "results": [
                {
                    "field": r.field,
                    "consensus": r.consensus_value,
                    "discrepancy_pct": r.discrepancy_pct,
                    "is_discrepant": r.is_discrepant,
                    "providers": r.provider_values
                }
                for r in discrepant[:20]  # Top 20
            ]
        }
    
    async def _check_quarantine(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Check quarantine statistics."""
        stats = await self.integrity_engine.get_quarantine_stats()
        return stats
    
    async def _review_quarantined(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Review and potentially release quarantined records."""
        quarantine_id = payload.get("quarantine_id")
        action = payload.get("action")  # "release" or "confirm"
        reviewer = payload.get("reviewer", "system")
        resolution = payload.get("resolution", "")
        
        if not quarantine_id:
            raise ValueError("quarantine_id required")
        
        if action == "release":
            record = await self.integrity_engine.quarantine.release(quarantine_id)
            if record:
                await self.integrity_engine.quarantine.review(quarantine_id, reviewer, "released", resolution)
                return {"status": "released", "record": record}
            else:
                return {"status": "not_found"}
        elif action == "confirm":
            await self.integrity_engine.quarantine.review(quarantine_id, reviewer, "confirmed", resolution)
            return {"status": "confirmed"}
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _get_verification_stats(self) -> Dict[str, Any]:
        """Get verification statistics."""
        quarantine_stats = await self.integrity_engine.get_quarantine_stats()
        
        return {
            "quarantine": quarantine_stats,
            "validation_history_count": len(self.integrity_engine._validation_history)
        }


if __name__ == "__main__":
    # Test
    import asyncio
    from erin.data_core import SourceRegistry, DataIntegrityEngine
    
    async def test():
        registry = SourceRegistry()
        await registry.initialize()
        
        integrity = DataIntegrityEngine(registry)
        await integrity.initialize()
        
        queue = asyncio.Queue()
        config = VerificationAgentConfig(agent_id="verification_001")
        
        agent = VerificationAgent(config, queue, registry, integrity)
        await agent.start()
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Verification agent test passed!")
    
    asyncio.run(test())

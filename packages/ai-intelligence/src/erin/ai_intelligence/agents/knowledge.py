"""
ERIN AI Intelligence - Knowledge Agent
Manages the knowledge base and entity relationships.
"""

import asyncio
from typing import Any, Dict, List, Optional

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.ai_intelligence import KnowledgeBase, EntityType, RelationType


class KnowledgeAgentConfig(AgentConfig):
    """Configuration for Knowledge Agent."""
    agent_type: str = "knowledge"
    name: str = "Knowledge Agent"
    description: str = "Manages the knowledge base and entity relationships"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.ACCESS_KNOWLEDGE_BASE,
        AgentPermission.MODIFY_KNOWLEDGE_BASE,
        AgentPermission.RUN_COMPUTATIONS,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["delete_entity", "delete_relation"])


class KnowledgeAgent(BaseAgent):
    """Agent that manages the knowledge base."""
    
    def __init__(self, config: KnowledgeAgentConfig, task_queue: asyncio.Queue, knowledge_base: KnowledgeBase, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.knowledge_base = knowledge_base
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute knowledge base tasks."""
        action = task.action
        
        if action == "create_company":
            return await self._create_company(task.payload)
        elif action == "create_security":
            return await self._create_security(task.payload)
        elif action == "link_financials":
            return await self._link_financials(task.payload)
        elif action == "add_relation":
            return await self._add_relation(task.payload)
        elif action == "find_path":
            return await self._find_path(task.payload)
        elif action == "get_neighbors":
            return await self._get_neighbors(task.payload)
        elif action == "search_entities":
            return await self._search_entities(task.payload)
        elif action == "get_entity_at_time":
            return await self._get_entity_at_time(task.payload)
        elif action == "get_kb_stats":
            return await self._get_kb_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _create_company(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a company entity."""
        name = payload.get("name")
        if not name:
            raise ValueError("name required")
        
        company = await self.knowledge_base.create_company(
            name=name,
            cik=payload.get("cik", ""),
            tickers=payload.get("tickers", {}),
            **{k: v for k, v in payload.items() if k not in ["name", "cik", "tickers"]}
        )
        
        return {
            "entity_id": company.entity_id,
            "name": company.name,
            "entity_type": company.entity_type.value
        }
    
    async def _create_security(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a security entity."""
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("symbol required")
        
        company_id = payload.get("company_id", "")
        
        security = await self.knowledge_base.create_security(
            symbol=symbol,
            figi=payload.get("figi", ""),
            company_id=company_id,
            **{k: v for k, v in payload.items() if k not in ["symbol", "figi", "company_id"]}
        )
        
        return {
            "entity_id": security.entity_id,
            "name": security.name,
            "entity_type": security.entity_type.value
        }
    
    async def _link_financials(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Link financial facts to a company."""
        company_id = payload.get("company_id")
        if not company_id:
            raise ValueError("company_id required")
        
        statement_type = payload.get("statement_type", "")
        period = payload.get("period", "")
        facts = payload.get("facts", [])
        source_id = payload.get("source_id", "")
        
        temporal_facts = await self.knowledge_base.link_financials(
            company_id, statement_type, period, facts, source_id
        )
        
        return {
            "linked_facts": len(temporal_facts),
            "fact_ids": [f.fact_id for f in temporal_facts]
        }
    
    async def _add_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add a relation between entities."""
        source_id = payload.get("source_entity_id")
        target_id = payload.get("target_entity_id")
        relation_type_str = payload.get("relation_type")
        
        if not all([source_id, target_id, relation_type_str]):
            raise ValueError("source_entity_id, target_entity_id, relation_type required")
        
        relation_type = RelationType(relation_type_str)
        
        relation = await self.knowledge_base.add_relation(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=relation_type,
            properties=payload.get("properties", {}),
            source_ids=payload.get("source_ids", [])
        )
        
        return {
            "relation_id": relation.relation_id,
            "source": source_id,
            "target": target_id,
            "type": relation_type.value
        }
    
    async def _find_path(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Find paths between entities."""
        source_id = payload.get("source_entity_id")
        target_id = payload.get("target_entity_id")
        max_depth = payload.get("max_depth", 3)
        
        if not source_id or not target_id:
            raise ValueError("source_entity_id and target_entity_id required")
        
        paths = await self.knowledge_base.find_path(source_id, target_id, max_depth)
        
        return {
            "paths_found": len(paths),
            "paths": [
                [
                    {
                        "relation_id": r.relation_id,
                        "source": r.source_entity_id,
                        "target": r.target_entity_id,
                        "type": r.relation_type.value
                    }
                    for r in path
                ]
                for path in paths
            ]
        }
    
    async def _get_neighbors(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get neighboring entities."""
        entity_id = payload.get("entity_id")
        max_depth = payload.get("max_depth", 1)
        
        if not entity_id:
            raise ValueError("entity_id required")
        
        neighbors = await self.knowledge_base.get_neighbors(entity_id, max_depth)
        
        return {
            "entity_id": entity_id,
            "neighbors": {
                depth: [
                    {
                        "entity_id": e.entity_id,
                        "name": e.name,
                        "type": e.entity_type.value
                    }
                    for e in entities
                ]
                for depth, entities in neighbors.items()
            }
        }
    
    async def _search_entities(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Search for entities."""
        query = payload.get("query", "")
        if not query:
            raise ValueError("query required")
        
        entity_types = payload.get("entity_types")
        if entity_types:
            entity_types = [EntityType(t) for t in entity_types]
        
        limit = payload.get("limit", 50)
        
        results = await self.knowledge_base.search(query, entity_types, limit)
        
        return {
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "entity_id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type.value,
                    "aliases": e.aliases[:5]
                }
                for e in results
            ]
        }
    
    async def _get_entity_at_time(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get entity state at a specific point in time."""
        entity_id = payload.get("entity_id")
        at_time_str = payload.get("at_time")
        
        if not entity_id or not at_time_str:
            raise ValueError("entity_id and at_time required")
        
        from datetime import datetime
        at_time = datetime.fromisoformat(at_time_str.replace("Z", "+00:00"))
        
        state = await self.knowledge_base.get_entity_at_time(entity_id, at_time)
        
        return {
            "entity_id": entity_id,
            "at_time": at_time_str,
            "state": state
        }
    
    async def _get_kb_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return await self.knowledge_base.get_stats()


if __name__ == "__main__":
    # Test
    import asyncio
    from erin.ai_intelligence import KnowledgeBase
    
    async def test():
        kb = KnowledgeBase("/tmp/test_kb2.db")
        await kb.initialize()
        
        queue = asyncio.Queue()
        config = KnowledgeAgentConfig(agent_id="knowledge_001")
        
        agent = KnowledgeAgent(config, queue, kb)
        await agent.start()
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Knowledge agent test passed!")
    
    asyncio.run(test())

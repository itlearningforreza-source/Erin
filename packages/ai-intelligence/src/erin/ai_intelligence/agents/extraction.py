"""
ERIN AI Intelligence - Extraction Agent
Processes documents and extracts financial facts.
"""

import asyncio
from typing import Any, Dict, List, Optional

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.data_core import DocumentPipeline, SourceRegistry


class ExtractionAgentConfig(AgentConfig):
    """Configuration for Extraction Agent."""
    agent_type: str = "extraction"
    name: str = "Extraction Agent"
    description: str = "Processes documents and extracts financial facts"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.ACCESS_EXTERNAL_API,
        AgentPermission.RUN_COMPUTATIONS,
        AgentPermission.ACCESS_KNOWLEDGE_BASE,
        AgentPermission.MODIFY_KNOWLEDGE_BASE,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["process_sensitive_doc"])


class ExtractionAgent(BaseAgent):
    """Agent that processes documents and extracts financial facts."""
    
    def __init__(self, config: ExtractionAgentConfig, task_queue: asyncio.Queue, registry: SourceRegistry, document_pipeline: DocumentPipeline, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.registry = registry
        self.document_pipeline = document_pipeline
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute extraction tasks."""
        action = task.action
        
        if action == "process_document":
            return await self._process_document(task.payload)
        elif action == "process_from_source":
            return await self._process_from_source(task.payload)
        elif action == "extract_financial_facts":
            return await self._extract_financial_facts(task.payload)
        elif action == "get_extraction_stats":
            return await self._get_extraction_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _process_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process a document and extract financial facts."""
        content = payload.get("content")
        if isinstance(content, str):
            content = content.encode('utf-8')
        elif not isinstance(content, bytes):
            raise ValueError("content must be bytes or string")
        
        filename = payload.get("filename", "")
        source_id = payload.get("source_id", "")
        source_url = payload.get("source_url", "")
        mime_type = payload.get("mime_type", "")
        
        result = await self.document_pipeline.process(content, filename, source_id, source_url, mime_type)
        
        return {
            "success": result.success,
            "document_id": result.document_metadata.document_id if result.document_metadata else None,
            "document_type": result.document_metadata.document_type.value if result.document_metadata else None,
            "tables_count": len(result.tables),
            "texts_count": len(result.texts),
            "facts_count": len(result.financial_facts),
            "entities_count": len(result.entities),
            "errors": result.errors,
            "warnings": result.warnings,
            "processing_time_ms": result.processing_time_ms
        }
    
    async def _process_from_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process documents from a registered source."""
        source_id = payload.get("source_id")
        if not source_id:
            raise ValueError("source_id required")
        
        source = await self.registry.get(source_id)
        if not source:
            raise ValueError(f"Source not found: {source_id}")
        
        # This would fetch documents from the source and process them
        # For now, return a placeholder
        return {
            "source_id": source_id,
            "status": "processing_not_implemented",
            "message": "Would fetch and process documents from source"
        }
    
    async def _extract_financial_facts(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract financial facts from already processed tables."""
        tables = payload.get("tables", [])
        period = payload.get("period", "")
        
        # Convert to ExtractedTable objects
        from erin.data_core.document_pipeline import ExtractedTable
        extracted_tables = [ExtractedTable(**t) for t in tables]
        
        facts = []
        from erin.data_core import FinancialStatementParser
        parser = FinancialStatementParser()
        
        for table in extracted_tables:
            stmt_type = parser.identify_statement_type(table)
            if stmt_type.value != "unknown":
                table_facts = parser.parse_statement(table, stmt_type, period)
                facts.extend([{
                    "concept": f.concept,
                    "value": f.value,
                    "unit": f.unit,
                    "period": f.period,
                    "statement_type": f.statement_type.value,
                    "page": f.page_reference,
                    "table_id": f.table_reference
                } for f in table_facts])
        
        return {
            "facts_count": len(facts),
            "facts": facts[:50]  # Limit to 50
        }
    
    async def _get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            "document_pipeline": "ready",
            "supported_types": ["pdf", "html", "xlsx", "csv", "json"],
            "statement_types": ["balance_sheet", "income_statement", "cash_flow", "changes_in_equity"]
        }


if __name__ == "__main__":
    # Test
    import asyncio
    from erin.data_core import SourceRegistry, DocumentPipeline
    
    async def test():
        registry = SourceRegistry()
        await registry.initialize()
        
        pipeline = DocumentPipeline()
        
        queue = asyncio.Queue()
        config = ExtractionAgentConfig(agent_id="extraction_001")
        
        agent = ExtractionAgent(config, queue, registry, pipeline)
        await agent.start()
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Extraction agent test passed!")
    
    asyncio.run(test())

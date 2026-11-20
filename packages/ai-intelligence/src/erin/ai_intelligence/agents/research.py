"""
ERIN AI Intelligence - Research Agent
Performs financial research and analysis.
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.ai_intelligence import KnowledgeBase
from erin.data_core import SourceRegistry


class ResearchAgentConfig(AgentConfig):
    """Configuration for Research Agent."""
    agent_type: str = "research"
    name: str = "Research Agent"
    description: str = "Performs financial research and analysis"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.READ_MARKET_DATA,
        AgentPermission.READ_FINANCIALS,
        AgentPermission.RUN_COMPUTATIONS,
        AgentPermission.ACCESS_KNOWLEDGE_BASE,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["publish_research"])


@dataclass
class ResearchReport:
    """A research report."""
    report_id: str = field(default_factory=lambda: f"rpt_{uuid.uuid4().hex[:12]}")
    title: str = ""
    entity_id: str = ""
    report_type: str = ""  # fundamental, technical, macro, risk
    sections: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "research_agent"


class ResearchAgent(BaseAgent):
    """Agent that performs financial research and generates reports."""
    
    def __init__(self, config: ResearchAgentConfig, task_queue: asyncio.Queue, registry: SourceRegistry, knowledge_base: KnowledgeBase, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.registry = registry
        self.knowledge_base = knowledge_base
        self._reports: List[ResearchReport] = []
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute research tasks."""
        action = task.action
        
        if action == "fundamental_analysis":
            return await self._fundamental_analysis(task.payload)
        elif action == "technical_analysis":
            return await self._technical_analysis(task.payload)
        elif action == "peer_comparison":
            return await self._peer_comparison(task.payload)
        elif action == "generate_report":
            return await self._generate_report(task.payload)
        elif action == "get_research_history":
            return await self._get_research_history(task.payload)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _fundamental_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform fundamental analysis on a company."""
        entity_id = payload.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id required")
        
        # Get company entity
        entity = await self.knowledge_base.get_entity(entity_id)
        if not entity or entity.entity_type.value != "company":
            raise ValueError("Entity not found or not a company")
        
        # Get temporal facts (financials)
        from datetime import datetime
        at_time = datetime.now(timezone.utc)
        
        facts = await self.knowledge_base.get_temporal_facts(entity_id, at_time=at_time)
        
        # Organize facts by statement type
        financials = {}
        for fact in facts:
            if fact.attribute.startswith(('balance_sheet.', 'income_statement.', 'cash_flow.')):
                stmt_type = fact.attribute.split('.')[0]
                concept = fact.attribute.split('.', 1)[1] if '.' in fact.attribute else fact.attribute
                if stmt_type not in financials:
                    financials[stmt_type] = {}
                financials[stmt_type][concept] = {
                    "value": fact.value,
                    "unit": fact.provenance.get('period', 'unknown')
                }
        
        # Calculate key ratios
        ratios = self._calculate_ratios(financials)
        
        return {
            "entity_id": entity_id,
            "company_name": entity.name,
            "analysis_time": at_time.isoformat(),
            "financials": financials,
            "ratios": ratios,
            "summary": self._generate_fundamental_summary(financials, ratios)
        }
    
    def _calculate_ratios(self, financials: Dict) -> Dict[str, Any]:
        """Calculate key financial ratios."""
        ratios = {}
        
        bs = financials.get('balance_sheet', {})
        is_ = financials.get('income_statement', {})
        cf = financials.get('cash_flow', {})
        
        # Liquidity ratios
        current_assets = bs.get('Current Assets', {}).get('value', 0)
        current_liabilities = bs.get('Current Liabilities', {}).get('value', 1)
        if current_liabilities:
            ratios['current_ratio'] = current_assets / current_liabilities
        
        cash = bs.get('Cash and Cash Equivalents', {}).get('value', 0)
        if current_liabilities:
            ratios['cash_ratio'] = cash / current_liabilities
        
        # Profitability ratios
        revenue = is_.get('Revenue', {}).get('value', 0)
        net_income = is_.get('Net Income', {}).get('value', 0)
        if revenue:
            ratios['net_margin'] = net_income / revenue
        
        total_assets = bs.get('Total Assets', {}).get('value', 0)
        if total_assets:
            ratios['roa'] = net_income / total_assets
        
        total_equity = bs.get('Total Equity', {}).get('value', 0)
        if total_equity:
            ratios['roe'] = net_income / total_equity
        
        # Leverage ratios
        total_liabilities = bs.get('Total Liabilities', {}).get('value', 0)
        if total_equity:
            ratios['debt_to_equity'] = total_liabilities / total_equity
        
        return ratios
    
    def _generate_fundamental_summary(self, financials: Dict, ratios: Dict) -> str:
        """Generate a summary of fundamental analysis."""
        parts = []
        
        if 'net_margin' in ratios:
            parts.append(f"Net margin: {ratios['net_margin']:.1%}")
        if 'roe' in ratios:
            parts.append(f"ROE: {ratios['roe']:.1%}")
        if 'current_ratio' in ratios:
            parts.append(f"Current ratio: {ratios['current_ratio']:.2f}")
        if 'debt_to_equity' in ratios:
            parts.append(f"Debt-to-equity: {ratios['debt_to_equity']:.2f}")
        
        return "; ".join(parts) if parts else "Insufficient data for summary"
    
    async def _technical_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform technical analysis (placeholder)."""
        return {
            "status": "not_implemented",
            "message": "Technical analysis would use market data from acquisition agent"
        }
    
    async def _peer_comparison(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compare company with peers."""
        entity_id = payload.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id required")
        
        entity = await self.knowledge_base.get_entity(entity_id)
        if not entity:
            raise ValueError("Entity not found")
        
        # Find peers by sector/industry
        sector = entity.properties.get('sector', '')
        industry = entity.properties.get('industry', '')
        
        peers = await self.knowledge_base.find_entities(sector, EntityType.COMPANY)
        peers = [p for p in peers if p.entity_id != entity_id][:10]
        
        return {
            "entity_id": entity_id,
            "company_name": entity.name,
            "sector": sector,
            "peers_found": len(peers),
            "peers": [
                {
                    "entity_id": p.entity_id,
                    "name": p.name,
                    "properties": {k: v for k, v in p.properties.items() if k in ['market_cap', 'revenue', 'net_income']}
                }
                for p in peers
            ]
        }
    
    async def _generate_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a research report."""
        import uuid
        
        report = ResearchReport(
            title=payload.get("title", "Research Report"),
            entity_id=payload.get("entity_id", ""),
            report_type=payload.get("report_type", "fundamental"),
            sections=payload.get("sections", {}),
            evidence=payload.get("evidence", []),
            conclusions=payload.get("conclusions", []),
            confidence=payload.get("confidence", 1.0)
        )
        
        self._reports.append(report)
        
        return {
            "report_id": report.report_id,
            "title": report.title,
            "entity_id": report.entity_id,
            "created_at": report.created_at.isoformat()
        }
    
    async def _get_research_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get research report history."""
        limit = payload.get("limit", 50)
        
        return {
            "reports": [
                {
                    "report_id": r.report_id,
                    "title": r.title,
                    "entity_id": r.entity_id,
                    "type": r.report_type,
                    "created_at": r.created_at.isoformat(),
                    "confidence": r.confidence
                }
                for r in self._reports[-limit:]
            ]
        }


if __name__ == "__main__":
    # Test
    import asyncio
    from erin.ai_intelligence import KnowledgeBase
    from erin.data_core import SourceRegistry
    
    async def test():
        registry = SourceRegistry()
        await registry.initialize()
        
        kb = KnowledgeBase("/tmp/test_kb3.db")
        await kb.initialize()
        
        queue = asyncio.Queue()
        config = ResearchAgentConfig(agent_id="research_001")
        
        agent = ResearchAgent(config, queue, registry, kb)
        await agent.start()
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Research agent test passed!")
    
    asyncio.run(test())

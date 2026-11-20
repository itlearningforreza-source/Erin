"""
ERIN AI Intelligence Package
Knowledge base, autonomous agents, and research engine.
"""

from erin.ai_intelligence.knowledge_base import (
    KnowledgeBase,
    KnowledgeEntity,
    KnowledgeRelation,
    TemporalFact,
    EntityType,
    RelationType,
    get_knowledge_base
)

from erin.ai_intelligence.agents import (
    BaseAgent,
    AgentConfig,
    AgentTask,
    AgentPermission,
    TaskPriority,
    AgentStatus,
    DiscoveryAgent,
    DiscoveryAgentConfig,
    AcquisitionAgent,
    AcquisitionAgentConfig,
    VerificationAgent,
    VerificationAgentConfig,
    ExtractionAgent,
    ExtractionAgentConfig,
    KnowledgeAgent,
    KnowledgeAgentConfig,
    ResearchAgent,
    ResearchAgentConfig,
    ResearchReport,
    MonitoringAgent,
    MonitoringAgentConfig,
    Alert,
    AlertSeverity,
    AgentOrchestrator,
    OrchestratorConfig,
    SystemTask,
    OrchestratorStatus,
    get_orchestrator
)

__all__ = [
    # Knowledge Base
    "KnowledgeBase",
    "KnowledgeEntity",
    "KnowledgeRelation",
    "TemporalFact",
    "EntityType",
    "RelationType",
    "get_knowledge_base",
    
    # Agents - Base
    "BaseAgent",
    "AgentConfig",
    "AgentTask",
    "AgentPermission",
    "TaskPriority",
    "AgentStatus",
    
    # Agents - Discovery
    "DiscoveryAgent",
    "DiscoveryAgentConfig",
    
    # Agents - Acquisition
    "AcquisitionAgent",
    "AcquisitionAgentConfig",
    
    # Agents - Verification
    "VerificationAgent",
    "VerificationAgentConfig",
    
    # Agents - Extraction
    "ExtractionAgent",
    "ExtractionAgentConfig",
    
    # Agents - Knowledge
    "KnowledgeAgent",
    "KnowledgeAgentConfig",
    
    # Agents - Research
    "ResearchAgent",
    "ResearchAgentConfig",
    "ResearchReport",
    
    # Agents - Monitoring
    "MonitoringAgent",
    "MonitoringAgentConfig",
    "Alert",
    "AlertSeverity",
    
    # Orchestrator
    "AgentOrchestrator",
    "OrchestratorConfig",
    "SystemTask",
    "OrchestratorStatus",
    "get_orchestrator",
]

__version__ = "0.1.0"

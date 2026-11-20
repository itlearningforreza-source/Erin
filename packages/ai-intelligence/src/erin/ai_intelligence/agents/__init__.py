"""
ERIN AI Intelligence - Autonomous Agents
All agent implementations and the central orchestrator.
"""

from erin.ai_intelligence.agents.base import (
    BaseAgent,
    AgentConfig,
    AgentTask,
    AgentPermission,
    TaskPriority,
    AgentStatus
)

from erin.ai_intelligence.agents.discovery import (
    DiscoveryAgent,
    DiscoveryAgentConfig
)

from erin.ai_intelligence.agents.acquisition import (
    AcquisitionAgent,
    AcquisitionAgentConfig
)

from erin.ai_intelligence.agents.verification import (
    VerificationAgent,
    VerificationAgentConfig
)

from erin.ai_intelligence.agents.extraction import (
    ExtractionAgent,
    ExtractionAgentConfig
)

from erin.ai_intelligence.agents.knowledge import (
    KnowledgeAgent,
    KnowledgeAgentConfig
)

from erin.ai_intelligence.agents.research import (
    ResearchAgent,
    ResearchAgentConfig,
    ResearchReport
)

from erin.ai_intelligence.agents.monitoring import (
    MonitoringAgent,
    MonitoringAgentConfig,
    Alert,
    AlertSeverity
)

from erin.ai_intelligence.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorConfig,
    SystemTask,
    OrchestratorStatus,
    get_orchestrator
)

__all__ = [
    # Base
    "BaseAgent",
    "AgentConfig",
    "AgentTask",
    "AgentPermission",
    "TaskPriority",
    "AgentStatus",
    
    # Discovery
    "DiscoveryAgent",
    "DiscoveryAgentConfig",
    
    # Acquisition
    "AcquisitionAgent",
    "AcquisitionAgentConfig",
    
    # Verification
    "VerificationAgent",
    "VerificationAgentConfig",
    
    # Extraction
    "ExtractionAgent",
    "ExtractionAgentConfig",
    
    # Knowledge
    "KnowledgeAgent",
    "KnowledgeAgentConfig",
    
    # Research
    "ResearchAgent",
    "ResearchAgentConfig",
    "ResearchReport",
    
    # Monitoring
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

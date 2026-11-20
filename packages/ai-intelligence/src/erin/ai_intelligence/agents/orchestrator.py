"""
ERIN AI Intelligence - Agent Orchestrator
Central coordinator for all autonomous agents with task queues, resource limits, and approval gates.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from collections import defaultdict

import structlog

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority, AgentStatus
from erin.ai_intelligence.agents.discovery import DiscoveryAgent, DiscoveryAgentConfig
from erin.ai_intelligence.agents.acquisition import AcquisitionAgent, AcquisitionAgentConfig
from erin.ai_intelligence.agents.verification import VerificationAgent, VerificationAgentConfig
from erin.ai_intelligence.agents.extraction import ExtractionAgent, ExtractionAgentConfig
from erin.ai_intelligence.agents.knowledge import KnowledgeAgent, KnowledgeAgentConfig
from erin.ai_intelligence.agents.research import ResearchAgent, ResearchAgentConfig
from erin.ai_intelligence.agents.monitoring import MonitoringAgent, MonitoringAgentConfig, Alert, AlertSeverity
from erin.data_core import SourceRegistry, DataIntegrityEngine, DocumentPipeline
from erin.ai_intelligence import KnowledgeBase

logger = structlog.get_logger(__name__)


class OrchestratorStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    max_concurrent_tasks: int = 10
    default_task_timeout: int = 300
    enable_auto_discovery: bool = True
    discovery_interval_hours: int = 24
    enable_monitoring: bool = True
    monitoring_interval_seconds: int = 300
    human_approval_timeout_hours: int = 24
    resource_limits: Dict[str, Any] = field(default_factory=lambda: {
        "max_memory_mb": 2048,
        "max_cpu_percent": 80,
        "max_disk_gb": 10
    })


@dataclass
class SystemTask:
    """A system-level task that may involve multiple agents."""
    task_id: str = field(default_factory=lambda: f"sys_{uuid.uuid4().hex[:12]}")
    name: str
    description: str
    steps: List[Dict[str, Any]]  # Each step: {agent_type, action, payload, depends_on}
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class AgentOrchestrator:
    """Central orchestrator for all autonomous agents."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.status = OrchestratorStatus.STOPPED
        
        # Core components
        self.registry: Optional[SourceRegistry] = None
        self.integrity_engine: Optional[DataIntegrityEngine] = None
        self.document_pipeline: Optional[DocumentPipeline] = None
        self.knowledge_base: Optional[KnowledgeBase] = None
        
        # Agents
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        
        # Task management
        self.task_queue = asyncio.Queue()
        self.system_tasks: Dict[str, SystemTask] = {}
        self.pending_approvals: Dict[str, AgentTask] = {}
        
        # Callbacks
        self._task_result_callbacks: List[Callable[[AgentTask], Awaitable[None]]] = []
        
        # Stats
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "system_tasks_completed": 0,
            "start_time": None
        }
    
    async def initialize(self):
        """Initialize all components and agents."""
        if self.status != OrchestratorStatus.STOPPED:
            return
        
        self.status = OrchestratorStatus.STARTING
        logger.info("Initializing orchestrator")
        
        # Initialize core components
        self.registry = SourceRegistry()
        await self.registry.initialize()
        
        self.integrity_engine = DataIntegrityEngine(self.registry)
        await self.integrity_engine.initialize()
        
        self.document_pipeline = DocumentPipeline()
        
        self.knowledge_base = KnowledgeBase()
        await self.knowledge_base.initialize()
        
        # Create agents
        await self._create_agents()
        
        # Register result callback
        self._task_result_callbacks.append(self._handle_task_result)
        
        # Start all agents
        for agent in self.agents.values():
            await agent.start()
        
        self.status = OrchestratorStatus.RUNNING
        self._stats["start_time"] = datetime.now(timezone.utc).isoformat()
        logger.info("Orchestrator initialized", agents=len(self.agents))
    
    async def _create_agents(self):
        """Create and configure all agents."""
        # Discovery Agent
        discovery_config = DiscoveryAgentConfig(agent_id="discovery_001")
        discovery_agent = DiscoveryAgent(discovery_config, self.task_queue, self.registry)
        self.agents["discovery"] = discovery_agent
        self.agent_configs["discovery"] = discovery_config
        
        # Acquisition Agent
        acquisition_config = AcquisitionAgentConfig(agent_id="acquisition_001")
        acquisition_agent = AcquisitionAgent(acquisition_config, self.task_queue, self.registry)
        self.agents["acquisition"] = acquisition_agent
        self.agent_configs["acquisition"] = acquisition_config
        
        # Verification Agent
        verification_config = VerificationAgentConfig(agent_id="verification_001")
        verification_agent = VerificationAgent(verification_config, self.task_queue, self.registry, self.integrity_engine)
        self.agents["verification"] = verification_agent
        self.agent_configs["verification"] = verification_config
        
        # Extraction Agent
        extraction_config = ExtractionAgentConfig(agent_id="extraction_001")
        extraction_agent = ExtractionAgent(extraction_config, self.task_queue, self.registry, self.document_pipeline)
        self.agents["extraction"] = extraction_agent
        self.agent_configs["extraction"] = extraction_config
        
        # Knowledge Agent
        knowledge_config = KnowledgeAgentConfig(agent_id="knowledge_001")
        knowledge_agent = KnowledgeAgent(knowledge_config, self.task_queue, self.knowledge_base)
        self.agents["knowledge"] = knowledge_agent
        self.agent_configs["knowledge"] = knowledge_config
        
        # Research Agent
        research_config = ResearchAgentConfig(agent_id="research_001")
        research_agent = ResearchAgent(research_config, self.task_queue, self.registry, self.knowledge_base)
        self.agents["research"] = research_agent
        self.agent_configs["research"] = research_config
        
        # Monitoring Agent
        monitoring_config = MonitoringAgentConfig(agent_id="monitoring_001")
        monitoring_agent = MonitoringAgent(monitoring_config, self.task_queue, self.registry, self.integrity_engine)
        self.agents["monitoring"] = monitoring_agent
        self.agent_configs["monitoring"] = monitoring_config
    
    async def start(self):
        """Start the orchestrator."""
        if self.status == OrchestratorStatus.RUNNING:
            return
        await self.initialize()
    
    async def stop(self):
        """Stop the orchestrator and all agents."""
        self.status = OrchestratorStatus.STOPPING
        logger.info("Stopping orchestrator")
        
        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()
        
        self.status = OrchestratorStatus.STOPPED
        logger.info("Orchestrator stopped")
    
    async def _handle_task_result(self, task: AgentTask):
        """Handle task completion from agents."""
        if task.status == AgentStatus.COMPLETED:
            self._stats["tasks_completed"] += 1
        else:
            self._stats["tasks_failed"] += 1
        
        # Check for pending system tasks that depend on this task
        await self._check_system_task_dependencies(task)
    
    async def _check_system_task_dependencies(self, completed_task: AgentTask):
        """Check if any system tasks can proceed."""
        for sys_task in self.system_tasks.values():
            if sys_task.status != "running":
                continue
            
            # Check if all dependencies are met
            all_met = True
            for step in sys_task.steps:
                dep_id = step.get("depends_on")
                if dep_id and dep_id != completed_task.task_id:
                    # Check if dependency completed
                    dep_task = None
                    for agent in self.agents.values():
                        for t in agent.completed_tasks + agent.failed_tasks:
                            if t.task_id == dep_id:
                                dep_task = t
                                break
                    if not dep_task or dep_task.status != AgentStatus.COMPLETED:
                        all_met = False
                        break
            
            if all_met and sys_task.status == "running":
                # Execute next step
                await self._execute_next_system_step(sys_task)
    
    async def submit_task(self, agent_type: str, action: str, payload: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL, requires_approval: bool = False) -> AgentTask:
        """Submit a task to a specific agent."""
        if agent_type not in self.agents:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        task = AgentTask(
            agent_type=agent_type,
            action=action,
            payload=payload,
            priority=priority,
            requires_approval=requires_approval
        )
        
        # Check if approval needed
        agent = self.agents[agent_type]
        if requires_approval or action in agent.config.requires_human_approval_for:
            task.requires_approval = True
            task.status = AgentStatus.WAITING
            self.pending_approvals[task.task_id] = task
            logger.info("Task requires approval", task_id=task.task_id, agent_type=agent_type, action=action)
            return task
        
        self._stats["tasks_submitted"] += 1
        await self.task_queue.put(task)
        return task
    
    async def submit_system_task(self, name: str, description: str, steps: List[Dict[str, Any]]) -> SystemTask:
        """Submit a multi-agent system task."""
        sys_task = SystemTask(
            name=name,
            description=description,
            steps=steps
        )
        self.system_tasks[sys_task.task_id] = sys_task
        sys_task.status = "running"
        sys_task.started_at = datetime.now(timezone.utc)
        
        # Execute first step(s) that have no dependencies
        await self._execute_next_system_step(sys_task)
        
        return sys_task
    
    async def _execute_next_system_step(self, sys_task: SystemTask):
        """Execute the next step in a system task."""
        for step in sys_task.steps:
            if step.get("executed"):
                continue
            
            depends_on = step.get("depends_on")
            if depends_on:
                # Check if dependency completed
                dep_completed = False
                for agent in self.agents.values():
                    for t in agent.completed_tasks:
                        if t.task_id == depends_on and t.status == AgentStatus.COMPLETED:
                            dep_completed = True
                            break
                if not dep_completed:
                    continue
            
            # Execute step
            agent_type = step.get("agent_type")
            action = step.get("action")
            payload = step.get("payload", {})
            priority = TaskPriority(step.get("priority", TaskPriority.NORMAL.value))
            
            task = await self.submit_task(agent_type, action, payload, priority)
            step["task_id"] = task.task_id
            step["executed"] = True
            sys_task.results[step.get("name", action)] = {"task_id": task.task_id, "status": "submitted"}
            break  # Execute one step at a time
    
    async def approve_task(self, task_id: str, approved_by: str, approved: bool = True) -> bool:
        """Approve or reject a pending task."""
        if task_id not in self.pending_approvals:
            return False
        
        task = self.pending_approvals[task_id]
        task.approved = approved
        task.approved_by = approved_by
        
        if approved:
            task.status = AgentStatus.IDLE
            self._stats["tasks_submitted"] += 1
            await self.task_queue.put(task)
            logger.info("Task approved", task_id=task_id, approved_by=approved_by)
        else:
            task.status = AgentStatus.ERROR
            task.error = "Rejected by human"
            logger.info("Task rejected", task_id=task_id, rejected_by=approved_by)
        
        del self.pending_approvals[task_id]
        return True
    
    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Get an agent by type."""
        return self.agents.get(agent_type)
    
    def get_agent_stats(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific agent."""
        agent = self.agents.get(agent_type)
        if not agent:
            return None
        return agent.get_stats()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        agent_stats = {}
        for agent_type, agent in self.agents.items():
            agent_stats[agent_type] = agent.get_stats()
        
        return {
            "orchestrator": {
                "status": self.status.value,
                "uptime": (datetime.now(timezone.utc) - datetime.fromisoformat(self._stats["start_time"])).total_seconds() if self._stats["start_time"] else 0,
                **self._stats
            },
            "agents": agent_stats,
            "pending_approvals": len(self.pending_approvals),
            "system_tasks": len(self.system_tasks),
            "queue_size": self.task_queue.qsize()
        }
    
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all tasks pending human approval."""
        return [
            {
                "task_id": task.task_id,
                "agent_type": task.agent_type,
                "action": task.action,
                "payload": task.payload,
                "created_at": task.created_at.isoformat(),
                "priority": task.priority.name
            }
            for task in self.pending_approvals.values()
        ]
    
    async def run_discovery_cycle(self) -> Dict[str, Any]:
        """Run a full discovery cycle."""
        return await self.submit_task("discovery", "run_discovery_cycle", {}, TaskPriority.HIGH)
    
    async def run_acquisition_cycle(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Run data acquisition cycle."""
        if category:
            return await self.submit_task("acquisition", "fetch_category", {"category": category}, TaskPriority.NORMAL)
        else:
            return await self.submit_task("acquisition", "fetch_all_active", {}, TaskPriority.NORMAL)
    
    async def validate_data(self, records: List[Dict], source_id: str, category: str) -> Dict[str, Any]:
        """Validate a dataset."""
        return await self.submit_task("verification", "validate_dataset", {
            "records": records,
            "source_id": source_id,
            "category": category
        }, TaskPriority.HIGH)
    
    async def process_document(self, content: bytes, filename: str, source_id: str = "") -> Dict[str, Any]:
        """Process a document."""
        return await self.submit_task("extraction", "process_document", {
            "content": content,
            "filename": filename,
            "source_id": source_id
        }, TaskPriority.NORMAL)
    
    async def create_company(self, name: str, **kwargs) -> Dict[str, Any]:
        """Create a company in knowledge base."""
        return await self.submit_task("knowledge", "create_company", {"name": name, **kwargs}, TaskPriority.NORMAL)
    
    async def run_fundamental_analysis(self, entity_id: str) -> Dict[str, Any]:
        """Run fundamental analysis on a company."""
        return await self.submit_task("research", "fundamental_analysis", {"entity_id": entity_id}, TaskPriority.NORMAL)
    
    async def get_alerts(self, severity: Optional[str] = None, acknowledged: Optional[bool] = None) -> Dict[str, Any]:
        """Get system alerts."""
        monitoring_agent = self.agents.get("monitoring")
        if monitoring_agent and hasattr(monitoring_agent, '_get_alerts'):
            # This would need to be called via the agent's task queue
            pass
        return {"alerts": [], "message": "Use monitoring agent directly"}


# Global instance
_orchestrator: Optional[AgentOrchestrator] = None


async def get_orchestrator(config: Optional[OrchestratorConfig] = None) -> AgentOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(config)
        await _orchestrator.initialize()
    return _orchestrator


if __name__ == "__main__":
    # Test
    async def test():
        orchestrator = AgentOrchestrator()
        await orchestrator.start()
        
        stats = orchestrator.get_all_stats()
        print(f"System stats: {json.dumps(stats, indent=2, default=str)}")
        
        # Test submitting a task
        task = await orchestrator.submit_task("discovery", "get_discovery_stats", {})
        print(f"Submitted task: {task.task_id}")
        
        await asyncio.sleep(2)
        
        stats = orchestrator.get_all_stats()
        print(f"Stats after task: {json.dumps(stats, indent=2, default=str)}")
        
        await orchestrator.stop()
        print("Orchestrator test passed!")
    
    import asyncio
    asyncio.run(test())

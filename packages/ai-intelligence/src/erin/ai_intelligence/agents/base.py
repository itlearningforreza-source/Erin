"""
ERIN AI Intelligence - Base Agent Classes
Foundation for all autonomous agents with permissions, task queues, and resource limits.
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, List, Dict, Callable, Awaitable
from collections import deque

import structlog

logger = structlog.get_logger(__name__)


class AgentPermission(str, Enum):
    """Permissions that agents can have."""
    READ_MARKET_DATA = "read_market_data"
    WRITE_MARKET_DATA = "write_market_data"
    READ_FINANCIALS = "read_financials"
    WRITE_FINANCIALS = "write_financials"
    EXECUTE_TRADES = "execute_trades"
    ACCESS_EXTERNAL_API = "access_external_api"
    RUN_COMPUTATIONS = "run_computations"
    ACCESS_KNOWLEDGE_BASE = "access_knowledge_base"
    MODIFY_KNOWLEDGE_BASE = "modify_knowledge_base"
    SEND_NOTIFICATIONS = "send_notifications"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    ERROR = "error"
    COMPLETED = "completed"


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


@dataclass
class AgentTask:
    """A task for an agent to execute."""
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    agent_type: str = ""
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: AgentStatus = AgentStatus.IDLE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    requires_approval: bool = False
    approved: bool = False
    approved_by: Optional[str] = None
    resource_limits: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str
    agent_type: str
    name: str
    description: str = ""
    permissions: List[AgentPermission] = field(default_factory=list)
    max_concurrent_tasks: int = 1
    default_timeout_seconds: int = 300
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"max_retries": 3, "backoff_factor": 2.0})
    requires_human_approval_for: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Base class for all autonomous agents."""
    
    def __init__(self, config: AgentConfig, task_queue: asyncio.Queue, result_callback: Optional[Callable[[AgentTask], Awaitable[None]]] = None):
        self.config = config
        self.task_queue = task_queue
        self.result_callback = result_callback
        self.status = AgentStatus.IDLE
        self.current_task: Optional[AgentTask] = None
        self.completed_tasks: List[AgentTask] = []
        self.failed_tasks: List[AgentTask] = []
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0,
            "last_activity": None
        }
    
    @abstractmethod
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute a specific task. Must be implemented by subclasses."""
        pass
    
    async def start(self):
        """Start the agent worker loop."""
        if self._running:
            return
        self._running = True
        self.status = AgentStatus.IDLE
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Agent started", agent_id=self.config.agent_id, type=self.config.agent_type)
    
    async def stop(self):
        """Stop the agent gracefully."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.status = AgentStatus.IDLE
        logger.info("Agent stopped", agent_id=self.config.agent_id)
    
    async def _worker_loop(self):
        """Main worker loop - processes tasks from queue."""
        while self._running:
            try:
                # Wait for task with timeout to allow checking _running flag
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                # Check if agent has permission for this task
                if not self._check_permissions(task):
                    task.status = AgentStatus.ERROR
                    task.error = f"Insufficient permissions for action: {task.action}"
                    await self._complete_task(task)
                    continue
                
                # Check if task requires human approval
                if task.requires_approval and not task.approved:
                    task.status = AgentStatus.WAITING
                    logger.info("Task waiting for approval", task_id=task.task_id, agent_id=self.config.agent_id)
                    # Re-queue for later
                    await self.task_queue.put(task)
                    await asyncio.sleep(5)
                    continue
                
                # Execute task
                await self._execute_task(task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker loop error", agent_id=self.config.agent_id, error=str(e))
                await asyncio.sleep(5)
    
    def _check_permissions(self, task: AgentTask) -> bool:
        """Check if agent has required permissions for task."""
        # Map actions to required permissions
        action_permissions = {
            "fetch_data": AgentPermission.READ_MARKET_DATA,
            "store_data": AgentPermission.WRITE_MARKET_DATA,
            "fetch_financials": AgentPermission.READ_FINANCIALS,
            "store_financials": AgentPermission.WRITE_FINANCIALS,
            "execute_trade": AgentPermission.EXECUTE_TRADES,
            "call_api": AgentPermission.ACCESS_EXTERNAL_API,
            "compute": AgentPermission.RUN_COMPUTATIONS,
            "query_kb": AgentPermission.ACCESS_KNOWLEDGE_BASE,
            "update_kb": AgentPermission.MODIFY_KNOWLEDGE_BASE,
            "notify": AgentPermission.SEND_NOTIFICATIONS,
        }
        
        required_permission = action_permissions.get(task.action)
        if required_permission and required_permission not in self.config.permissions:
            return False
        return True
    
    async def _execute_task(self, task: AgentTask):
        """Execute a single task with error handling and timeout."""
        self.status = AgentStatus.RUNNING
        self.current_task = task
        task.status = AgentStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Apply timeout
            result = await asyncio.wait_for(
                self.execute_task(task),
                timeout=self.config.default_timeout_seconds
            )
            
            task.result = result
            task.status = AgentStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            
            execution_time = (task.completed_at - start_time).total_seconds()
            self._stats["tasks_completed"] += 1
            self._stats["total_execution_time"] += execution_time
            self._stats["last_activity"] = task.completed_at.isoformat()
            
            logger.info("Task completed", task_id=task.task_id, agent_id=self.config.agent_id, duration=execution_time)
            
        except asyncio.TimeoutError:
            task.status = AgentStatus.ERROR
            task.error = f"Task timed out after {self.config.default_timeout_seconds} seconds"
            logger.warning("Task timeout", task_id=task.task_id, agent_id=self.config.agent_id)
            
        except Exception as e:
            task.status = AgentStatus.ERROR
            task.error = str(e)
            self._stats["tasks_failed"] += 1
            logger.error("Task failed", task_id=task.task_id, agent_id=self.config.agent_id, error=str(e))
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                backoff = self.config.retry_policy.get("backoff_factor", 2.0) ** task.retry_count
                logger.info("Retrying task", task_id=task.task_id, attempt=task.retry_count, backoff=backoff)
                await asyncio.sleep(backoff)
                await self.task_queue.put(task)
                return
        
        finally:
            await self._complete_task(task)
    
    async def _complete_task(self, task: AgentTask):
        """Handle task completion."""
        self.current_task = None
        self.status = AgentStatus.IDLE
        
        if task.status == AgentStatus.COMPLETED:
            self.completed_tasks.append(task)
        else:
            self.failed_tasks.append(task)
        
        # Keep only last 1000 tasks in memory
        if len(self.completed_tasks) > 1000:
            self.completed_tasks = self.completed_tasks[-1000:]
        if len(self.failed_tasks) > 1000:
            self.failed_tasks = self.failed_tasks[-1000:]
        
        if self.result_callback:
            try:
                await self.result_callback(task)
            except Exception as e:
                logger.error("Result callback failed", error=str(e))
    
    def submit_task(self, action: str, payload: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL, requires_approval: bool = False) -> AgentTask:
        """Submit a new task to this agent."""
        task = AgentTask(
            agent_type=self.config.agent_type,
            action=action,
            payload=payload,
            priority=priority,
            requires_approval=requires_approval or action in self.config.requires_human_approval_for,
            max_retries=self.config.retry_policy.get("max_retries", 3)
        )
        # Note: In practice, this would go through the orchestrator
        return task
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent_id": self.config.agent_id,
            "agent_type": self.config.agent_type,
            "status": self.status.value,
            "current_task": self.current_task.task_id if self.current_task else None,
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "queue_size": self.task_queue.qsize(),
            **self._stats
        }
    
    def get_recent_tasks(self, limit: int = 50) -> List[AgentTask]:
        """Get recent completed and failed tasks."""
        all_tasks = self.completed_tasks + self.failed_tasks
        all_tasks.sort(key=lambda t: t.completed_at or t.started_at or datetime.min, reverse=True)
        return all_tasks[:limit]


if __name__ == "__main__":
    # Simple test
    import asyncio
    
    async def test():
        queue = asyncio.Queue()
        config = AgentConfig(
            agent_id="test_agent",
            agent_type="test",
            name="Test Agent",
            permissions=[AgentPermission.READ_MARKET_DATA, AgentPermission.RUN_COMPUTATIONS]
        )
        
        class TestAgent(BaseAgent):
            async def execute_task(self, task):
                await asyncio.sleep(0.1)
                return {"status": "ok", "input": task.payload}
        
        agent = TestAgent(config, queue)
        await agent.start()
        
        # Submit a task
        task = AgentTask(
            agent_type="test",
            action="compute",
            payload={"value": 42},
            priority=TaskPriority.NORMAL
        )
        await queue.put(task)
        
        # Wait for completion
        await asyncio.sleep(1)
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Base agent test passed!")
    
    asyncio.run(test())

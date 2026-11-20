"""Unit tests for Autonomous Agents."""

import asyncio
import pytest
import sys
sys.path.insert(0, '/home/rezaahmadkhairuddin/ERIN/packages/ai-intelligence/src')

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
    AgentOrchestrator,
    OrchestratorConfig
)
from erin.data_core import SourceRegistry


class TestBaseAgent:
    """Tests for BaseAgent."""
    
    @pytest.mark.asyncio
    async def test_agent_lifecycle(self):
        """Test agent start/stop lifecycle."""
        queue = asyncio.Queue()
        config = AgentConfig(
            agent_id="test_agent",
            agent_type="test",
            name="Test Agent",
            permissions=[AgentPermission.RUN_COMPUTATIONS]
        )
        
        class TestAgent(BaseAgent):
            async def execute_task(self, task):
                await asyncio.sleep(0.01)
                return {"result": "ok"}
        
        agent = TestAgent(config, queue)
        
        # Test start
        await agent.start()
        assert agent.status == AgentStatus.IDLE
        
        # Submit task
        task = AgentTask(
            agent_type="test",
            action="compute",
            payload={"value": 42},
            priority=TaskPriority.NORMAL
        )
        await queue.put(task)
        
        # Wait for completion
        await asyncio.sleep(0.1)
        
        # Check stats
        stats = agent.get_stats()
        assert stats["tasks_completed"] == 1
        assert stats["tasks_failed"] == 0
        
        await agent.stop()
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_task_retry(self):
        """Test task retry on failure."""
        queue = asyncio.Queue()
        config = AgentConfig(
            agent_id="test_agent",
            agent_type="test",
            name="Test Agent",
            permissions=[AgentPermission.RUN_COMPUTATIONS]
        )
        
        attempt_count = 0
        
        class FlakyAgent(BaseAgent):
            async def execute_task(self, task):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count < 2:
                    raise ValueError("Temporary failure")
                return {"result": "success"}
        
        agent = FlakyAgent(config, queue)
        await agent.start()
        
        task = AgentTask(
            agent_type="test",
            action="compute",
            payload={},
            priority=TaskPriority.NORMAL,
            max_retries=3
        )
        await queue.put(task)
        
        await asyncio.sleep(0.2)  # Wait for retries
        
        stats = agent.get_stats()
        assert stats["tasks_completed"] == 1
        assert attempt_count == 2  # Initial + 1 retry
        
        await agent.stop()
    
    @pytest.mark.asyncio
    async def test_permission_check(self):
        """Test that permissions are checked."""
        queue = asyncio.Queue()
        config = AgentConfig(
            agent_id="test_agent",
            agent_type="test",
            name="Test Agent",
            permissions=[AgentPermission.RUN_COMPUTATIONS]  # No ACCESS_EXTERNAL_API
        )
        
        class TestAgent(BaseAgent):
            async def execute_task(self, task):
                return {"result": "ok"}
        
        agent = TestAgent(config, queue)
        await agent.start()
        
        # Task requiring ACCESS_EXTERNAL_API should be rejected
        task = AgentTask(
            agent_type="test",
            action="call_api",  # Requires ACCESS_EXTERNAL_API
            payload={},
            priority=TaskPriority.NORMAL
        )
        await queue.put(task)
        
        await asyncio.sleep(0.1)
        
        stats = agent.get_stats()
        assert stats["tasks_failed"] == 1
        
        await agent.stop()


class TestDiscoveryAgent:
    """Tests for DiscoveryAgent."""
    
    @pytest.mark.asyncio
    async def test_discovery_agent_creation(self):
        """Test that discovery agent can be created."""
        registry = SourceRegistry()
        await registry.initialize()
        
        queue = asyncio.Queue()
        config = DiscoveryAgentConfig(agent_id="discovery_test")
        
        agent = DiscoveryAgent(config, queue, registry)
        await agent.start()
        
        stats = agent.get_stats()
        assert stats["agent_type"] == "discovery"
        
        await agent.stop()


class TestAcquisitionAgent:
    """Tests for AcquisitionAgent."""
    
    @pytest.mark.asyncio
    async def test_acquisition_agent_creation(self):
        """Test that acquisition agent can be created."""
        registry = SourceRegistry()
        await registry.initialize()
        
        queue = asyncio.Queue()
        config = AcquisitionAgentConfig(agent_id="acquisition_test")
        
        agent = AcquisitionAgent(config, queue, registry)
        await agent.start()
        
        stats = agent.get_stats()
        assert stats["agent_type"] == "acquisition"
        
        await agent.stop()


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initializes all agents."""
        orchestrator = AgentOrchestrator()
        await orchestrator.start()
        
        assert orchestrator.status.value == "running"
        assert len(orchestrator.agents) == 7  # discovery, acquisition, verification, extraction, knowledge, research, monitoring
        
        stats = orchestrator.get_all_stats()
        assert "orchestrator" in stats
        assert "agents" in stats
        assert len(stats["agents"]) == 7
        
        await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test submitting a task through orchestrator."""
        orchestrator = AgentOrchestrator()
        await orchestrator.start()
        
        task = await orchestrator.submit_task("discovery", "get_discovery_stats", {})
        assert task.task_id.startswith("task_")
        assert task.agent_type == "discovery"
        assert task.action == "get_discovery_stats"
        
        await asyncio.sleep(0.1)
        
        stats = orchestrator.get_all_stats()
        assert stats["orchestrator"]["tasks_submitted"] == 1
        
        await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_approval_workflow(self):
        """Test human approval workflow."""
        orchestrator = AgentOrchestrator()
        await orchestrator.start()
        
        # Submit task requiring approval
        task = await orchestrator.submit_task(
            "discovery",
            "register_source",  # Requires approval
            {},
            requires_approval=True
        )
        
        # Task should be pending approval
        assert task.requires_approval is True
        assert task.status.value == "waiting"
        
        # Approve
        approved = await orchestrator.approve_task(task.task_id, "tester", True)
        assert approved is True
        
        # Task should now be in queue
        await asyncio.sleep(0.1)
        
        stats = orchestrator.get_all_stats()
        assert stats["orchestrator"]["tasks_submitted"] == 1
        
        await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_system_task(self):
        """Test multi-step system task."""
        orchestrator = AgentOrchestrator()
        await orchestrator.start()
        
        sys_task = await orchestrator.submit_system_task(
            "Test Workflow",
            "Run discovery then acquisition",
            [
                {"name": "discover", "agent_type": "discovery", "action": "get_discovery_stats", "payload": {}},
                {"name": "acquire", "agent_type": "acquisition", "action": "get_fetch_stats", "payload": {}, "depends_on": "{{discover.task_id}}"}
            ]
        )
        
        assert sys_task.task_id.startswith("sys_")
        assert sys_task.status == "running"
        
        await asyncio.sleep(0.5)
        
        stats = orchestrator.get_all_stats()
        assert stats["orchestrator"]["tasks_submitted"] >= 2
        
        await orchestrator.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

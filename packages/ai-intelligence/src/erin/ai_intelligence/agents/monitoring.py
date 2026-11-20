"""
ERIN AI Intelligence - Monitoring Agent
Monitors system health, data freshness, and anomalies.
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

from erin.ai_intelligence.agents.base import BaseAgent, AgentConfig, AgentTask, AgentPermission, TaskPriority
from erin.data_core import SourceRegistry, DataIntegrityEngine


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """System alert."""
    alert_id: str = field(default_factory=lambda: f"alt_{uuid.uuid4().hex[:12]}")
    severity: AlertSeverity
    title: str
    description: str
    source: str  # agent_id or component
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class MonitoringAgentConfig(AgentConfig):
    """Configuration for Monitoring Agent."""
    agent_type: str = "monitoring"
    name: str = "Monitoring Agent"
    description: str = "Monitors system health, data freshness, and anomalies"
    permissions: List[AgentPermission] = field(default_factory=lambda: [
        AgentPermission.READ_MARKET_DATA,
        AgentPermission.RUN_COMPUTATIONS,
        AgentPermission.SEND_NOTIFICATIONS,
    ])
    requires_human_approval_for: List[str] = field(default_factory=lambda: ["send_alert"])


class MonitoringAgent(BaseAgent):
    """Agent that monitors system health and data quality."""
    
    def __init__(self, config: MonitoringAgentConfig, task_queue: asyncio.Queue, registry: SourceRegistry, integrity_engine: DataIntegrityEngine, result_callback=None):
        super().__init__(config, task_queue, result_callback)
        self.registry = registry
        self.integrity_engine = integrity_engine
        self._alerts: List[Alert] = []
        self._monitoring_enabled = True
        self._check_interval_seconds = config.resource_limits.get("check_interval_seconds", 300)  # 5 minutes
        self._staleness_threshold_hours = config.resource_limits.get("staleness_threshold_hours", 24)
        self._failure_threshold = config.resource_limits.get("failure_threshold", 5)
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the agent and monitoring loop."""
        await super().start()
        if self._monitoring_enabled:
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop(self):
        """Stop the agent and monitoring loop."""
        self._monitoring_enabled = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        await super().stop()
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_enabled:
            try:
                await self._run_health_checks()
            except Exception as e:
                logger.error("Monitoring loop error", error=str(e))
            
            await asyncio.sleep(self._check_interval_seconds)
    
    async def _run_health_checks(self):
        """Run all health checks."""
        await self._check_source_health()
        await self._check_data_freshness()
        await self._check_integrity_stats()
        await self._check_quarantine_backlog()
    
    async def _check_source_health(self):
        """Check health of all sources."""
        sources = await self.registry.list_sources(limit=1000)
        
        for source in sources:
            # Check if source has failed recently
            if source.consecutive_failures >= self._failure_threshold:
                self._create_alert(
                    AlertSeverity.CRITICAL,
                    f"Source {source.name} has {source.consecutive_failures} consecutive failures",
                    f"monitoring_agent",
                    {"source_id": source.source_id, "failures": source.consecutive_failures}
                )
            
            # Check if source is degraded
            if source.operational_status.value == "degraded":
                self._create_alert(
                    AlertSeverity.WARNING,
                    f"Source {source.name} is degraded",
                    f"monitoring_agent",
                    {"source_id": source.source_id}
                )
    
    async def _check_data_freshness(self):
        """Check if data is stale."""
        sources = await self.registry.list_sources(limit=1000)
        
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=self._staleness_threshold_hours)
        
        for source in sources:
            if source.last_successful_fetch and source.last_successful_fetch < threshold:
                hours_stale = (now - source.last_successful_fetch).total_seconds() / 3600
                self._create_alert(
                    AlertSeverity.WARNING,
                    f"Source {source.name} data is stale ({hours_stale:.1f} hours old)",
                    f"monitoring_agent",
                    {"source_id": source.source_id, "hours_stale": hours_stale}
                )
    
    async def _check_integrity_stats(self):
        """Check data integrity statistics."""
        stats = await self.integrity_engine.get_quarantine_stats()
        
        pending = stats.get("pending_review", 0)
        if pending > 100:
            self._create_alert(
                AlertSeverity.WARNING,
                f"Quarantine backlog: {pending} records pending review",
                f"monitoring_agent",
                {"pending_count": pending}
            )
    
    async def _check_quarantine_backlog(self):
        """Check quarantine backlog growth."""
        # This would track growth rate over time
        pass
    
    def _create_alert(self, severity: AlertSeverity, description: str, source: str, metadata: Dict[str, Any]):
        """Create a new alert."""
        alert = Alert(
            severity=severity,
            title=description,
            description=description,
            source=source,
            metadata=metadata
        )
        self._alerts.append(alert)
        
        # Keep only last 1000 alerts
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]
        
        logger.warning("Alert created", alert_id=alert.alert_id, severity=severity.value, description=description)
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute monitoring tasks."""
        action = task.action
        
        if action == "get_alerts":
            return await self._get_alerts(task.payload)
        elif action == "acknowledge_alert":
            return await self._acknowledge_alert(task.payload)
        elif action == "run_health_check":
            await self._run_health_checks()
            return {"status": "completed"}
        elif action == "get_monitoring_stats":
            return await self._get_monitoring_stats()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _get_alerts(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get alerts with filters."""
        severity = payload.get("severity")
        acknowledged = payload.get("acknowledged")
        limit = payload.get("limit", 100)
        
        alerts = self._alerts
        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return {
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "severity": a.severity.value,
                    "title": a.title,
                    "description": a.description,
                    "source": a.source,
                    "created_at": a.created_at.isoformat(),
                    "acknowledged": a.acknowledged,
                    "metadata": a.metadata
                }
                for a in alerts[:limit]
            ],
            "total": len(alerts)
        }
    
    async def _acknowledge_alert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Acknowledge an alert."""
        alert_id = payload.get("alert_id")
        acknowledged_by = payload.get("acknowledged_by", "system")
        
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now(timezone.utc)
                alert.acknowledged_by = acknowledged_by
                return {"status": "acknowledged", "alert_id": alert_id}
        
        return {"status": "not_found"}
    
    async def _get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        total_alerts = len(self._alerts)
        unacknowledged = len([a for a in self._alerts if not a.acknowledged])
        by_severity = {}
        for alert in self._alerts:
            by_severity[alert.severity.value] = by_severity.get(alert.severity.value, 0) + 1
        
        return {
            "total_alerts": total_alerts,
            "unacknowledged": unacknowledged,
            "by_severity": by_severity,
            "monitoring_enabled": self._monitoring_enabled,
            "check_interval_seconds": self._check_interval_seconds
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
        config = MonitoringAgentConfig(agent_id="monitoring_001")
        
        agent = MonitoringAgent(config, queue, registry, integrity)
        await agent.start()
        
        await asyncio.sleep(1)
        
        stats = agent.get_stats()
        print(f"Stats: {stats}")
        
        await agent.stop()
        print("Monitoring agent test passed!")
    
    asyncio.run(test())

# Runbook: High Error Rate

## Alert
**Alert**: `HighErrorRate`  
**Severity**: Critical  
**SLO Impact**: Availability (< 99.99%)

## Description
Error rate exceeds 1% for 5 minutes on a service. Indicates systemic failure affecting users.

## Impact
- Users experiencing failed requests
- Potential data loss or inconsistency
- SLO breach (availability < 99.99%)

## Diagnosis Steps

### 1. Identify Affected Service
```bash
# Check which service is alerting
kubectl get pods -n erin-platform -l app.kubernetes.io/name=market-data-api

# Check recent deployments
kubectl rollout history deployment/market-data-api -n erin-platform
```

### 2. Check Error Patterns
```bash
# View recent logs for errors
kubectl logs -n erin-platform -l app.kubernetes.io/name=market-data-api --tail=100 | grep -i error

# Check specific error types
kubectl logs -n erin-platform -l app.kubernetes.io/name=market-data-api --tail=500 | jq -r 'select(.level=="ERROR") | .message' | sort | uniq -c | sort -rn
```

### 3. Check Dependencies
```bash
# Database connectivity
kubectl exec -n erin-platform deploy/market-data-api -- pg_isready -h postgresql.erin-data.svc.cluster.local

# Redis connectivity
kubectl exec -n erin-platform deploy/market-data-api -- redis-cli -h redis.erin-data.svc.cluster.local ping

# Kafka connectivity
kubectl exec -n erin-platform deploy/market-data-api -- kafka-broker-api-versions --bootstrap-server kafka.erin-data.svc.cluster.local:9092
```

### 4. Check Resource Constraints
```bash
# Resource usage
kubectl top pods -n erin-platform -l app.kubernetes.io/name=market-data-api

# Events
kubectl get events -n erin-platform --sort-by=.metadata.creationTimestamp | tail -20
```

### 5. Check Recent Changes
```bash
# Recent deployments
kubectl rollout history deployment/market-data-api -n erin-platform

# Config changes
kubectl get configmap erin-config -n erin-platform -o yaml
```

## Resolution Steps

### If Recent Deployment
```bash
# Rollback to previous version
kubectl rollout undo deployment/market-data-api -n erin-platform

# Verify rollout
kubectl rollout status deployment/market-data-api -n erin-platform
```

### If Database Issue
```bash
# Check connection pool
kubectl exec -n erin-data postgresql-0 -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check for locks
kubectl exec -n erin-data postgresql-0 -- psql -U postgres -c "SELECT * FROM pg_locks WHERE NOT granted;"
```

### If Redis Issue
```bash
# Check memory
kubectl exec -n erin-data redis-master-0 -- redis-cli INFO memory

# Check connected clients
kubectl exec -n erin-data redis-master-0 -- redis-cli CLIENT LIST
```

### If Kafka Issue
```bash
# Check consumer lag
kubectl exec -n erin-data kafka-0 -- kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group market-data-api --describe

# Check under-replicated partitions
kubectl exec -n erin-data kafka-0 -- kafka-topics.sh --bootstrap-server localhost:9092 --describe --under-replicated-partitions
```

### If Resource Exhaustion
```bash
# Scale up deployment
kubectl scale deployment market-data-api -n erin-platform --replicas=10

# Or add node (if using cluster autoscaler)
```

## Post-Resolution
1. Verify error rate returns to normal (< 0.1%)
2. Verify latency returns to normal (< 100ms p99)
3. Document root cause in incident tracker
4. Schedule postmortem within 48 hours
5. Update runbook if new failure mode discovered

## Escalation
| Time | Action |
|------|--------|
| 5 min | On-call acknowledges |
| 15 min | No resolution → Escalate to team lead |
| 30 min | No resolution → Escalate to engineering manager |
| 60 min | No resolution → Escalate to VP Engineering |

## Related Runbooks
- [High Latency](./high-latency.md)
- [Database Connection Issues](./database-connections.md)
- [Kafka Consumer Lag](./kafka-consumer-lag.md)
- [Pod Restart Loop](./pod-restart-loop.md)
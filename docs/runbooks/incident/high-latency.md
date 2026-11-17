# Runbook: High Latency

## Alert
**Alert**: `HighLatency`  
**Severity**: Warning  
**SLO Impact**: Latency (p99 < 100ms)

## Description
p99 latency exceeds 1 second for 5 minutes on a service. Users experiencing slow responses.

## Impact
- Degraded user experience
- Potential timeout cascades
- SLO breach risk (latency p99 < 100ms)

## Diagnosis Steps

### 1. Identify Bottleneck
```bash
# Check service latency breakdown
curl -s http://localhost:9090/api/v1/query?query=histogram_quantile\(0.99,sum\(rate\(http_request_duration_seconds_bucket[5m]\)\)\)by\(le,service\)

# Check specific endpoint latency
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,sum(rate(http_request_duration_seconds_bucket{handler=\"/api/v1/market-data/quotes\"}[5m]))by(le))"
```

### 2. Check Resource Saturation
```bash
# CPU throttling
kubectl top pods -n erin-platform -l app.kubernetes.io/name=market-data-api --containers

# Memory pressure
kubectl exec -n erin-platform deploy/market-data-api -- cat /proc/meminfo

# Disk I/O
kubectl exec -n erin-platform deploy/market-data-api -- iostat -x 1 3
```

### 3. Check Database Performance
```bash
# Slow queries
kubectl exec -n erin-data postgresql-0 -- psql -U postgres -c "
SELECT query, calls, mean_exec_time, max_exec_time, rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 10;"

# Connection pool
kubectl exec -n erin-data postgresql-0 -- psql -U postgres -c "
SELECT count(*) as active, max_connections, 
       (count(*)::float / max_connections * 100) as usage_pct
FROM pg_stat_activity, pg_settings
WHERE name = 'max_connections';"
```

### 3. Check Redis Latency
```bash
# Redis latency
kubectl exec -n erin-data redis-master-0 -- redis-cli --latency-history -i 1

# Slowlog
kubectl exec -n erin-data redis-master-0 -- redis-cli SLOWLOG GET 10
```

### 4. Check Network
```bash
# Pod-to-pod latency
kubectl exec -n erin-platform deploy/market-data-api -- ping -c 5 postgresql.erin-data.svc.cluster.local

# Service mesh latency (if Istio)
istioctl proxy-config routes deploy/market-data-api.erin-platform -o json | jq .
```

## Resolution Steps

### If CPU Saturation
```bash
# Scale horizontally
kubectl scale deployment market-data-api -n erin-platform --replicas=15

# Or optimize code (profile first)
# py-spy record -o profile.svg --pid <pid>
```

### If Database Slow
```bash
# Add read replica
# Or optimize queries (add indexes)
# Or increase connection pool

# Check for missing indexes
kubectl exec -n erin-data postgresql-0 -- psql -U postgres -c "
SELECT schemaname, tablename, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan AND seq_tup_read > 10000
ORDER BY seq_tup_read DESC;"
```

### If Redis Slow
```bash
# Check memory pressure
kubectl exec -n erin-data redis-master-0 -- redis-cli INFO memory

# Check for large keys
kubectl exec -n erin-data redis-master-0 -- redis-cli --bigkeys

# Increase memory or add replicas
```

### If Network/Service Mesh
```bash
# Check sidecar resource usage
kubectl top pods -n erin-platform -l app.kubernetes.io/name=market-data-api --containers

# Restart sidecar if needed
kubectl exec -n erin-platform deploy/market-data-api -c istio-proxy -- kill 1
```

### If Kafka Lag
```bash
# Increase consumer parallelism
kubectl scale deployment market-data-api -n erin-platform --replicas=10

# Or increase consumer threads in application config
```

## Post-Resolution
1. Verify p99 latency returns to < 100ms
2. Verify error rate remains low
3. Document root cause
4. Schedule postmortem if SLO breached

## Related Runbooks
- [High Error Rate](./high-error-rate.md)
- [Database Connection Issues](./database-connections.md)
- [Kafka Consumer Lag](./kafka-consumer-lag.md)
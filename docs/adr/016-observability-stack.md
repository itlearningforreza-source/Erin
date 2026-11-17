# ADR 016: Observability Stack - Prometheus, Grafana, Loki, Tempo

## Status
Accepted

## Context
As ERIN scales to a distributed microservices architecture, we need comprehensive observability covering:

- **Metrics**: System health, business KPIs, SLOs
- **Logs**: Structured, searchable, correlated
- **Traces**: Distributed request flow, latency analysis
- **Alerting**: Actionable, routed, deduplicated

## Decision
We adopt the **Grafana LGTM Stack** (Loki, Grafana, Tempo, Mimir/Prometheus) with the following components:

### 1. Metrics: Prometheus + Thanos
- **Prometheus**: Short-term (30d), high-resolution metrics
- **Thanos**: Long-term storage (1yr+), global query, downsampling
- **Targets**: 100k+ series, 30s scrape interval
- **Retention**: 30d hot (Prometheus), 1yr cold (Thanos/S3)

### 2. Logs: Loki + Promtail
- **Loki**: Log aggregation, label-based indexing
- **Promtail**: Agent on each node, Kubernetes SD
- **Retention**: 30 days hot, 1 year cold (S3)
- **Query**: LogQL, integrated with Grafana

### 3. Traces: Tempo
- **Tempo**: Trace storage, TraceQL
- **Sampling**: 10% tail-based, 100% error traces
- **Retention**: 30 days hot, 90 days cold
- **Integration**: Exemplars from Prometheus, logs correlation

### 4. Visualization: Grafana
- **Dashboards**: Infrastructure, Business, SLO, ML
- **Alerting**: Unified alerting (Prometheus + Loki + Tempo)
- **Plugins**: Kubernetes, Kafka, PostgreSQL, Redis

### 5. Alerting: Alertmanager + Grafana Alerting
- **Routes**: Critical → PagerDuty, Warning → Slack/Email
- **Grouping**: By service, severity, namespace
- **Inhibition**: Critical inhibits warning for same service

## Metrics Strategy

### 1. Golden Signals (per service)
| Signal | Metric | Target |
|--------|--------|--------|
| Latency | `http_request_duration_seconds{quantile="0.99"}` | < 100ms p99 |
| Traffic | `rate(http_requests_total[5m])` | > 0 |
| Errors | `rate(http_requests_total{status=~"5.."}[5m])` | < 0.1% |
| Saturation | `container_cpu_usage / container_spec_cpu_quota` | < 80% |

### 2. Business Metrics
| Domain | Metrics |
|--------|---------|
| Market Data | `quotes_per_second`, `staleness_seconds`, `provider_latency` |
| Trading | `orders_per_second`, `fill_rate`, `rejection_rate`, `latency_p99` |
| Portfolio | `total_aum`, `daily_pnl`, `var_95`, `margin_usage` |
| Risk | `var_95_1d`, `stress_test_pnl`, `limit_utilization` |
| Data Quality | `ingestion_lag`, `schema_violations`, `missing_data_points` |

### 3. Infrastructure Metrics
| Component | Key Metrics |
|-----------|-------------|
| Kubernetes | `pod_restarts`, `cpu_throttling`, `memory_pressure`, `disk_pressure` |
| PostgreSQL | `connections_active`, `query_duration_p99`, `replication_lag`, `cache_hit_ratio` |
| Redis | `memory_used_pct`, `hit_rate`, `connected_clients`, `evictions` |
| Kafka | `consumer_lag`, `under_replicated_partitions`, `request_latency_p99` |

## Logging Strategy

### Structured Logging (JSON)
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "service": "market-data-api",
  "trace_id": "abc123",
  "span_id": "def456",
  "message": "Quote fetched",
  "symbol": "AAPL",
  "latency_ms": 12,
  "provider": "yfinance"
}
```

### Log Levels
| Level | Use Case | Retention |
|-------|----------|-----------|
| DEBUG | Detailed debugging | 7 days |
| INFO | Business events, state changes | 30 days |
| WARN | Recoverable issues, retries | 90 days |
| ERROR | Failed operations, data loss | 1 year |

### Labels for Loki
```yaml
labels:
  - service
  - namespace
  - pod
  - container
  - severity
  - environment
```

## Tracing Strategy

### Sampling Strategy
| Scenario | Sampling Rate |
|----------|---------------|
| Normal requests | 10% (probabilistic) |
| Errors (5xx) | 100% |
| High latency (>1s) | 100% |
| Business-critical (orders, trades) | 100% |
| Health checks | 0% |

### Span Attributes (OpenTelemetry Semantic Conventions)
```yaml
required:
  - service.name
  - service.namespace
  - service.instance.id
  - trace.id
  - span.id
  - parent.span.id
  - span.kind
  - span.name
  - start.time
  - end.time
  - status.code
  - status.message
recommended:
  - http.method
  - http.route
  - http.status_code
  - http.target
  - db.system
  - db.operation
  - db.statement
  - messaging.system
  - messaging.destination
  - messaging.operation
custom:
  - erin.symbol
  - erin.portfolio_id
  - erin.order_id
  - erin.user_id
```

## Alerting Strategy

### Alert Categories
| Category | Severity | Response Time | Escalation |
|----------|----------|---------------|------------|
| Critical (SLO breach) | Critical | 5 min | PagerDuty → On-call |
| Warning (SLO risk) | Warning | 30 min | Slack + Email |
| Info (Operational) | Info | 4 hours | Slack |

### Key Alerts
```yaml
groups:
- name: slo-alerts
  rules:
  - alert: HighErrorRate
    expr: |
      sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
      /
      sum(rate(http_requests_total[5m])) by (service)
      > 0.01
    for: 5m
    labels:
      severity: critical
      slo: availability
    annotations:
      summary: "Error rate > 1% on {{ $labels.service }}"
      runbook: "https://runbooks.erin.io/high-error-rate"

  - alert: HighLatency
    expr: |
      histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)) > 1
    for: 5m
    labels:
      severity: warning
      slo: latency
    annotations:
      summary: "p99 latency > 1s on {{ $labels.service }}"
      runbook: "https://runbooks.erin.io/high-latency"

  - alert: HighConsumerLag
    expr: kafka_consumergroup_lag > 1000
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Kafka consumer lag > 1000"
      runbook: "https://runbooks.erin.io/kafka-lag"
```

## Implementation Plan
1. **Week 1**: Deploy Prometheus + Grafana + Alertmanager
2. **Week 2**: Deploy Loki + Promtail + Tempo
3. **Week 3**: Instrument all services with OpenTelemetry
4. **Week 4**: Build standard dashboards, configure alerts
5. **Week 5**: Define SLOs, error budgets, burn rate alerts
6. **Week 6**: Run chaos experiments, tune alerts

## SLO Definitions
| Service | Availability | Latency (p99) | Error Rate |
|---------|-------------|---------------|------------|
| Market Data API | 99.99% | < 100ms | < 0.01% |
| Charts API | 99.95% | < 500ms | < 0.1% |
| Portfolio API | 99.99% | < 200ms | < 0.01% |
| Order API | 99.99% | < 50ms | < 0.001% |
| Risk API | 99.95% | < 2s | < 0.1% |

## Cost Optimization
| Component | Monthly Cost | Optimization |
|-----------|-------------|--------------|
| Prometheus | $500 | Remote write to Thanos, downsampling |
| Loki | $800 | Compression, structured metadata |
| Tempo | $600 | Sampling, trace compression |
| Grafana Cloud | $500 | Self-hosted alternative |
| **Total** | **~$2,400/mo** | |

## References
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Google SRE Workbook - SLOs](https://sre.google/workbook/table-of-contents/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Loki Best Practices](https://grafana.com/docs/loki/latest/best-practices/)
- [Tempo Architecture](https://grafana.com/docs/tempo/latest/architecture/)
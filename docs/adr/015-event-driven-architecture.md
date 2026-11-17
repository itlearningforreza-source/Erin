# ADR 015: Event-Driven Architecture with Apache Kafka

## Status
Accepted

## Context
ERIN 2.0 currently uses synchronous REST APIs for all inter-service communication. As we scale to multiple microservices, we need:

- Decoupled services for independent scaling and deployment
- Resilience to partial failures
- Audit trail for financial transactions
- Real-time data streaming for ML features
- Event sourcing for regulatory compliance (MiFID II, SEC 17a-4)

## Decision
We will adopt **Apache Kafka** as our event backbone with the following architecture:

### 1. Event Categories

| Category | Topics | Retention | Partitions |
|----------|--------|-----------|------------|
| Market Data | `market.ticks`, `market.bars`, `market.quotes` | 7 days | 12 |
| Orders | `orders.placed`, `orders.filled`, `orders.cancelled`, `orders.rejected` | 7 years | 12 |
| Portfolio | `portfolio.created`, `portfolio.updated`, `portfolio.rebalanced` | 7 years | 6 |
| Risk | `risk.var_calculated`, `risk.stress_test_completed`, `risk.limit_breach` | 7 years | 6 |
| Market Data Ingestion | `ingestion.raw`, `ingestion.normalized`, `ingestion.failed` | 30 days | 12 |
| ML Features | `features.computed`, `features.drift_detected` | 90 days | 6 |
| Audit | `audit.user_action`, `audit.data_access`, `audit.config_change` | 7 years | 6 |

### 2. Event Schema (Avro)
```json
{
  "type": "record",
  "name": "MarketTick",
  "namespace": "com.erin.events.market",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_type", "type": "string"},
    "name": "timestamp", "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "source", "type": "string"},
    {"name": "payload", "type": {
      "type": "record",
      "name": "MarketTickPayload",
      "fields": [
        {"name": "symbol", "type": "string"},
        {"name": "price", "type": {"type": "bytes", "logicalType": "decimal", "precision": 19, "scale": 4}},
        {"name": "volume", "type": "long"},
        {"name": "bid", "type": ["null", {"type": "bytes", "logicalType": "decimal", "precision": 19, "scale": 4}]},
        {"name": "ask", "type": ["null", {"type": "bytes", "logicalType": "decimal", "precision": 19, "scale": 4}]},
        {"name": "timestamp", "type": {"type": "long", "logicalType": "timestamp-millis"}},
        {"name": "provider", "type": "string"}
      ]
    }}
  ]
}
```

### 3. Producer Patterns
- **Transactional Outbox**: For database changes (orders, portfolios) - write to outbox table + Kafka in same transaction
- **Direct Produce**: For high-volume market data (bypass database)
- **CDC**: Debezium for legacy database changes

### 4. Consumer Patterns
- **Event Sourcing**: Order service, Portfolio service - rebuild state from events
- **CQRS Read Models**: Portfolio snapshots, risk reports, dashboards
- **Stream Processing**: Flink for real-time aggregations, risk calculations
- **ML Feature Store**: Materialized views for feature serving

### 5. Schema Registry
- **Confluent Schema Registry** (or Apicurio)
- **Compatibility**: BACKWARD_TRANSITIVE
- **Governance**: Schema evolution rules, breaking change detection

### 4. Topic Configuration
```properties
# Market data - high throughput, short retention
market.ticks: partitions=12, retention=7d, cleanup.policy=delete,compression=snappy
market.bars: partitions=12, retention=7d, cleanup.policy=delete,compression=snappy

# Financial transactions - long retention, compacted
orders.placed: partitions=12, retention=7y, cleanup.policy=compact,min.insync.replicas=2
portfolio.rebalanced: partitions=6, retention=7y, cleanup.policy=compact,min.insync.replicas=2

# Audit - immutable
audit.*: partitions=6, retention=7y, cleanup.policy=compact,min.insync.replicas=3
```

## Consequences

### Positive
- Loose coupling between services
- Independent scaling of producers/consumers
- Replay capability for debugging, backtesting, ML training
- Audit trail for compliance
- Real-time ML feature computation
- Resilience to consumer failures (replay from offset)

### Negative
- Increased complexity (distributed system challenges)
- Eventual consistency model
- Schema evolution governance required
- Additional infrastructure (Kafka cluster, Schema Registry)
- Debugging distributed traces more complex

### Risks
- Data loss if not configured properly (mitigated by acks=all, min.insync.replicas)
- Schema evolution breaking consumers (mitigated by compatibility checks)
- Topic proliferation (mitigated by topic governance)
- Consumer lag during traffic spikes (mitigated by auto-scaling consumers)

## Implementation Plan
1. **Week 1**: Deploy Kafka cluster (3 brokers, 3 ZK), Schema Registry
2. **Week 2**: Define core schemas, set up compatibility checks in CI
2. **Week 3**: Implement transactional outbox for order service
3. **Week 4**: Migrate market data ingestion to Kafka
4. **Week 5**: Build stream processing (Flink) for real-time aggregations
5. **Week 6**: Implement event sourcing for order/portfolio services

## Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| RabbitMQ | Simpler, mature | No log retention, no replay, limited throughput | Rejected |
| AWS Kinesis | Managed | Vendor lock-in, cost at scale, no compacted topics | Rejected |
| Pulsar | Multi-tenancy, tiered storage | Smaller ecosystem, operational complexity | Future consideration |
| NATS JetStream | Lightweight, fast | Less mature ecosystem | Rejected |
| EventBridge | Serverless, AWS integration | Limited replay, vendor lock-in | Rejected |

## References
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/index.html)
- [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)
- [Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
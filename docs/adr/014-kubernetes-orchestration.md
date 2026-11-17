# ADR 014: Kubernetes Orchestration for ERIN Platform

## Status
Accepted

## Context
ERIN 2.0 has been developed as a monolithic FastAPI application running locally with Vite frontend. As we move toward production, we need a robust orchestration platform that provides:

- Horizontal scaling based on load
- High availability and fault tolerance
- Zero-downtime deployments
- Resource isolation between services
- Observability and monitoring
- Security and compliance
- GitOps-based deployment

## Decision
We will adopt **Kubernetes (EKS)** as our orchestration platform with the following key decisions:

### 1. Kubernetes Distribution: Amazon EKS
- **Rationale**: Managed control plane, integrated with AWS ecosystem, IAM integration (IRSA), mature ecosystem
- **Version**: Kubernetes 1.28 (current LTS)

### 2. Node Group Strategy
| Node Group | Instance Types | Purpose | Scaling |
|------------|---------------|---------|---------|
| system | m6i.large | Control plane, system pods | 2-10 |
| platform | m6i.xlarge, m6i.2xlarge | API services, business logic | 3-20 |
| data | r6i.xlarge, r6i.2xlarge | Databases, caches, Kafka | 2-10 |
| ml | g5.xlarge, g5.2xlarge | ML training, inference | 0-5 (spot) |

### 3. Networking
- **CNI**: AWS VPC CNI with custom networking
- **Service Mesh**: Istio for mTLS, traffic management, observability
- **Ingress**: NGINX Ingress Controller with cert-manager
- **DNS**: ExternalDNS with Route53

### 4. Storage
- **EBS**: GP3 for databases, caches (GP3 for cost/performance)
- **EFS**: Shared storage for notebooks, models
- **S3**: Long-term storage, backups, ML artifacts

### 5. Security
- **IRSA**: IAM Roles for Service Accounts
- **mTLS**: Istio mutual TLS
- **Secrets**: External Secrets Operator + AWS Secrets Manager
- **Network Policies**: Default deny, explicit allow
- **Pod Security Standards**: Restricted

### 6. GitOps
- **ArgoCD**: Declarative continuous delivery
- **App of Apps**: Pattern for managing applications
- **Sync Windows**: Automated with manual approval for production

### 7. Observability Stack
- **Prometheus + Thanos**: Metrics with long-term storage
- **Grafana**: Dashboards and alerting
- **Loki**: Log aggregation
- **Tempo**: Distributed tracing
- **Alertmanager**: Alert routing and notification

## Consequences

### Positive
- Industry-standard, well-supported platform
- Auto-scaling based on custom metrics
- Zero-downtime deployments with rollback capability
- Strong ecosystem and community
- Integrated with AWS services (IAM, Secrets Manager, etc.)

### Negative
- Increased operational complexity
- Requires Kubernetes expertise
- Additional cost for control plane ($73/month)
- Learning curve for team

### Risks
- Vendor lock-in to AWS (mitigated by using standard K8s APIs)
- EKS control plane upgrades require planning
- Cost optimization requires active FinOps

## Implementation Plan
1. **Week 1**: Provision EKS cluster with Terraform
2. **Week 2**: Install core addons (VPC CNI, CoreDNS, kube-proxy, CSI drivers)
3. **Week 3**: Deploy service mesh (Istio), ingress, cert-manager
4. **Week 4**: Deploy monitoring stack, logging, tracing
5. **Week 5**: Migrate market-data service as pilot
6. **Week 6**: Migrate remaining services, enable GitOps

## Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| ECS Fargate | Simpler, serverless | Less control, no GPUs, vendor lock-in | Rejected |
| GKE | Better K8s integration | Multi-cloud complexity | Rejected |
| Self-managed K8s | Full control | High operational burden | Rejected |
| Nomad | Simpler | Smaller ecosystem | Rejected |

## References
- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Istio Documentation](https://istio.io/latest/docs/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
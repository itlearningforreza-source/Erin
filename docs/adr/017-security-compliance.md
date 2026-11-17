# ADR 017: Security and Compliance Framework

## Status
Accepted

## Context
ERIN handles sensitive financial data and must comply with multiple regulatory frameworks:
- **SOX** (Sarbanes-Oxley) - Financial reporting integrity
- **GDPR** - Data protection and privacy
- **MiFID II** - Market transparency, best execution
- **SEC 17a-4** - Record retention, audit trails
- **PCI DSS** - Payment card data (if applicable)
- **SOC 2 Type II** - Security, availability, confidentiality

## Decision
We implement a **Zero Trust Security Architecture** with defense-in-depth across all layers.

## 1. Identity & Access Management

### 1.1 Authentication
| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| API | JWT (RS256) | Short-lived (15min) + refresh tokens |
| Service-to-Service | mTLS (Istio) | SPIFFE/SPIRE workload identity |
| Human | OIDC (Google/Microsoft) | MFA required, SSO |
| CI/CD | OIDC tokens | Short-lived, scoped to repo |

### 1.2 Authorization (RBAC + ABAC)
```yaml
roles:
  - name: admin
    permissions: ["*"]
  - name: trader
    permissions: ["order:*", "portfolio:read", "risk:read"]
  - name: analyst
    permissions: ["market:read", "fundamental:read", "analytics:read"]
  - name: compliance
    permissions: ["audit:read", "report:*"]
  - name: developer
    permissions: ["deploy:staging", "logs:read", "metrics:read"]

attributes:
  - portfolio_id (resource ownership)
  - region (data residency)
  - clearance_level (data sensitivity)
```

### 1.3 Privileged Access
- **Just-in-Time (JIT)**: Temporary elevation via approval workflow
- **Session Recording**: All privileged sessions recorded
- **Break-glass**: Emergency access with automatic alerting

## 2. Data Protection

### 2.1 Encryption
| State | Algorithm | Key Management |
|-------|-----------|----------------|
| At Rest (DB) | AES-256-GCM | AWS KMS + envelope encryption |
| At Rest (S3) | AES-256 | SSE-KMS with customer-managed keys |
| In Transit | TLS 1.3 | mTLS (Istio) + TLS 1.3 |
| In Memory | AES-256 | Application-level field encryption |

### 2.2 Key Management
- **AWS KMS**: Customer-managed keys (CMK) per environment
- **Key Rotation**: Annual automatic + on-demand
- **Key Hierarchy**: Master → Data Encryption Keys (DEK) → Field Keys
- **HSM**: CloudHSM for root keys (FIPS 140-2 Level 3)

### 2.3 Data Classification
| Level | Examples | Encryption | Access | Retention |
|-------|----------|------------|--------|-----------|
| Public | Market data, public filings | TLS only | Public | 7 years |
| Internal | Config, logs, metrics | TLS + AES-256 | Authenticated users | 3 years |
| Confidential | PII, credentials, keys | AES-256 + envelope | Role-based + MFA | 7 years |
| Restricted | Trade secrets, algorithms | AES-256 + HSM | JIT + approval | 7+ years |

### 2.4 Data Lifecycle
| Action | Implementation |
|--------|----------------|
| Classification | Automated tagging at ingestion |
| Retention | Automated policies per classification |
| Deletion | Cryptographic erasure (key destruction) |
| Archival | Cold storage (S3 Glacier) with integrity checks |
| Backup | Encrypted, cross-region, point-in-time recovery |

## 3. Network Security

### 3.1 Zero Trust Network
- **Default Deny**: All traffic blocked by default
- **Micro-segmentation**: Network policies per service
- **Service Mesh**: Istio mTLS, authorization policies
- **Egress Control**: Explicit allowlist for external APIs

### 3.2 Network Zones
```
┌─────────────────────────────────────────────────────┐
│                    Internet                          │
└─────────────────────────┬───────────────────────────┘
                          │
                    ┌─────▼─────┐
                    │   WAF     │ ← Rate limiting, DDoS, OWASP rules
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │  Ingress  │ ← TLS termination, auth, rate limiting
                    └─────┬─────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │ Public  │       │Private  │       │  Data   │
   │  Zone   │       │  Zone   │       │  Zone   │
   │(Ingress)│       │(APIs)   │       │(DB,Redis)│
   └────┬────┘       └────┬────┘       └────┬────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                    ┌─────▼─────┐
                    │  Egress   │ ← Explicit allowlist
                    └───────────┘
```

### 3.3 Egress Control
| Destination | Policy |
|-------------|--------|
| Data Providers (YFinance, OpenBB, FRED) | Allowlist IPs + mTLS |
| Cloud APIs (AWS, S3, KMS) | VPC Endpoints |
| Monitoring (Grafana Cloud) | Allowlist |
| Package Registries | Private mirrors only |
| All other | Deny |

## 4. Application Security

### 4.1 Secure Development
| Practice | Tool | Gate |
|----------|------|------|
| SAST | Semgrep, Bandit | PR |
| DAST | OWASP ZAP | Staging |
| SCA | Dependabot, Trivy | PR + Scheduled |
| Secrets Detection | TruffleHog, Gitleaks | Pre-commit + PR |
| Container Scan | Trivy, Grype | Build |
| IaC Scan | Checkov, tfsec | PR |

### 4.2 Runtime Security
- **Falco**: Kernel-level threat detection
- **Kyverno**: Admission controller policies
- **OPA Gatekeeper**: Constraint enforcement
- **Image Signing**: Cosign + Sigstore

### 4.3 Container Hardening
```dockerfile
# Base image: distroless or alpine
FROM gcr.io/distroless/python3:3.12

# Non-root user
USER 1000:1000

# Read-only root filesystem
# No shell, no package manager
# Minimal attack surface
```

## 5. Compliance Frameworks

### 5.1 SOX (Sarbanes-Oxley)
| Requirement | Implementation |
|-------------|----------------|
| Section 302 | CEO/CFO certify financial reports |
| Section 404 | Internal controls over financial reporting |
| Audit Trail | Immutable logs (Kafka + WORM storage) |
| Change Control | GitOps + signed commits + approval gates |
| Access Review | Quarterly automated + annual manual |

### 5.2 GDPR
| Requirement | Implementation |
|-------------|----------------|
| Lawful Basis | Legitimate interest + consent |
| Data Minimization | Schema validation, field-level encryption |
| Right to Access | Self-service portal + API |
| Right to Erasure | Cryptographic erasure (key destruction) |
| Data Portability | Standard export formats (JSON, CSV) |
| DPIA | Automated for new processing activities |
| DPO | Designated Data Protection Officer |

### 5.3 MiFID II
| Requirement | Implementation |
|-------------|----------------|
| Best Execution | TCA + venue analysis, quarterly reports |
| Transaction Reporting | RTS 22/23 automated |
| Clock Synchronization | NTP + PTP, <1ms accuracy |
| Record Keeping | 7 years, WORM storage, searchable |
| Algorithm Registration | RTS 6 compliance |

### 5.4 SEC 17a-4
| Requirement | Implementation |
|-------------|----------------|
| Retention | 7 years (6 years readily accessible) |
| WORM Storage | S3 Object Lock + Glacier Vault Lock |
| Audit Trail | Immutable Kafka + signed logs |
| Search/Retrieval | <24 hours for first 2 years |
| Independent Audit | Annual third-party |

### 5.5 SOC 2 Type II
| Trust Criteria | Controls |
|----------------|----------|
| Security | WAF, mTLS, RBAC, Vuln mgmt, IR plan |
| Availability | 99.99% SLA, HA, DR, Chaos eng |
| Confidentiality | Encryption, DLP, Access control |
| Processing Integrity | Idempotency, Exactly-once, Validation |
| Privacy | Data minimization, Consent, DPIA |

## 6. Incident Response

### 6.1 Response Plan
| Phase | Actions | Owner | Timeline |
|-------|---------|-------|----------|
| Detect | Alert → Triage → Severity | On-call | < 5 min |
| Contain | Isolate → Block → Preserve | IR Team | < 30 min |
| Eradicate | Root cause → Patch → Verify | IR Team | < 4 hours |
| Recover | Restore → Validate → Monitor | Platform | < 24 hours |
| Lessons | Postmortem → Action items | All | < 7 days |

### 6.2 Communication
| Audience | Channel | Timeline |
|----------|---------|----------|
| Internal | Slack #incidents, PagerDuty | Immediate |
| Customers | Status page, Email | < 30 min (SEV-1) |
| Regulators | Email, Portal | Per regulation |
| Public | Blog, Twitter | If public impact |

## 7. Audit & Monitoring

### 7.1 Continuous Compliance
| Check | Frequency | Tool |
|-------|-----------|------|
| Config drift | Continuous | Kyverno + GitOps |
| Vulnerability scan | Daily | Trivy |
| Secret scan | Per commit | TruffleHog |
| Access review | Quarterly | Automated + Manual |
| Penetration test | Quarterly | External |
| Compliance audit | Annual | Third-party |

### 7.2 Evidence Collection
- **Automated**: Config snapshots, vulnerability reports, access logs
- **Structured**: Markdown + JSON for auditor consumption
- **Retention**: 7 years in WORM storage

## Implementation Priority
| Phase | Focus | Timeline |
|-------|-------|----------|
| 1 | Identity, Encryption, Network Segmentation | Weeks 1-4 |
| 2 | Application Security, Runtime Protection | Weeks 5-8 |
| 3 | Compliance Automation, Evidence Collection | Weeks 9-12 |
| 4 | Penetration Test, SOC 2 Audit | Weeks 13-16 |

## References
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Kubernetes Benchmarks](https://www.cisecurity.org/benchmark/kubernetes)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [FFIEC IT Examination Handbook](https://ithandbook.ffiec.gov/)
# Runbook: Production Deployment

## Overview
This runbook covers the standard production deployment process for ERIN platform services using ArgoCD GitOps.

## Prerequisites
- [ ] ArgoCD CLI configured with production cluster access
- [ ] GitHub release tagged (semver)
- [ ] CHANGELOG.md updated
- [ ] Release notes approved by product/engineering
- [ ] Database migrations tested in staging
- [ ] Security scan passed (Trivy, Bandit, pip-audit)

## Pre-Deployment Checklist

### 1. Verify Release Artifacts
```bash
# Verify Docker image exists
docker pull ghcr.io/erin-org/erin-platform:1.2.3

# Verify image signature
cosign verify ghcr.io/erin-org/erin-platform:1.2.3 \
  --certificate-identity-regexp="https://github.com/erin-org/.github/workflows/.github/workflows/ci-cd.yaml@refs/heads/main" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

### 2. Verify Staging Deployment
```bash
# Check staging health
curl -sf https://api-staging.erin.io/health
curl -sf https://api-staging.erin.io/api/v1/market-data/quotes?symbols=AAPL

# Run smoke tests
./scripts/smoke-tests.sh staging
```

### 3. Verify Database Migrations
```bash
# Check pending migrations
kubectl exec -n erin-platform deploy/market-data-api -- alembic current
kubectl exec -n erin-platform deploy/market-data-api -- alembic history --verbose

# Run migration dry-run
kubectl exec -n erin-platform deploy/market-data-api -- alembic upgrade --sql head
```

## Deployment Process

### 1. Create GitHub Release
```bash
# Tag the release
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3

# Create GitHub release (auto-triggers CI/CD)
# Or manually via GitHub UI
```

### 2. Monitor ArgoCD Sync
```bash
# Watch ArgoCD application
argocd app get erin-platform-production --watch

# Or via UI
# https://argocd.erin.io/applications/erin-platform-production
```

### 3. Monitor Rollout
```bash
# Watch deployment rollout
kubectl rollout status deployment/market-data-api -n erin-platform --timeout=600s

# Check pod readiness
kubectl get pods -n erin-platform -l app.kubernetes.io/name=market-data-api -w
```

### 4. Verify Health
```bash
# Health checks
curl -sf https://api.erin.io/health
curl -sf https://api.erin.io/ready

# API functionality
curl -sf "https://api.erin.io/api/v1/market-data/quotes?symbols=AAPL,MSFT"
curl -sf "https://api.erin.io/api/v1/charts/data?symbol=AAPL&timeframe=1D"
curl -sf "https://api.erin.io/api/v1/portfolios/"
```

### 5. Run Post-Deployment Tests
```bash
# Run smoke test suite
./scripts/smoke-tests.sh production

# Run integration tests
pytest tests/integration/ -v --env=production
```

## Rollback Procedure

### If Critical Issues Detected
```bash
# Option 1: ArgoCD Rollback (preferred)
argocd app rollback erin-platform-production <revision>

# Option 2: Kubernetes Rollback
kubectl rollout undo deployment/market-data-api -n erin-platform

# Option 3: Git Revert (if code issue)
git revert <commit-hash>
git push origin main
# ArgoCD will auto-sync
```

### Verify Rollback
```bash
# Check rollout status
kubectl rollout status deployment/market-data-api -n erin-platform

# Verify health
curl -sf https://api.erin.io/health
curl -sf "https://api.erin.io/api/v1/market-data/quotes?symbols=AAPL"
```

## Post-Deployment

### 1. Monitor for 30 Minutes
```bash
# Watch key metrics
watch -n 30 'curl -s https://api.erin.io/health && curl -s "https://api.erin.io/api/v1/market-data/quotes?symbols=AAPL" | jq .[0].last.value'
```

### 2. Update Documentation
- [ ] Update CHANGELOG.md
- [ ] Update API documentation if API changed
- [ ] Update runbooks if new failure modes
- [ ] Update architecture diagrams if architecture changed

### 3. Notify Stakeholders
- [ ] Post deployment announcement in #deployments
- [ ] Update status page
- [ ] Notify product team of new features

## Emergency Contacts
| Role | Name | Contact |
|------|------|---------|
| Release Manager | | |
| Platform Lead | | |
| Engineering Manager | | |
| VP Engineering | | |
| On-call Engineer | | PagerDuty |

## Rollback Decision Matrix
| Symptom | Action |
|---------|--------|
| Error rate > 1% | Immediate rollback |
| p99 latency > 2s | Rollback if not resolved in 10 min |
| Critical feature broken | Immediate rollback |
| Minor bug (non-critical) | Hotfix forward |
| Performance regression | Rollback if > 20% degradation |

## Post-Deployment Monitoring (First 24 Hours)
| Metric | Threshold | Action |
|--------|-----------|--------|
| Error rate | > 0.1% | Investigate |
| p99 latency | > 200ms | Investigate |
| CPU usage | > 85% | Scale up |
| Memory usage | > 85% | Investigate/Scale |
| Database connections | > 80% | Increase pool |
| Kafka consumer lag | > 1000 | Scale consumers |
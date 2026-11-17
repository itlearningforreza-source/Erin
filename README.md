# ERIN 2.0

**Enterprise Research, Investment & Intelligence Network**  
*Production-Ready • Institutional-Grade • Open Source*

[![Build Status](https://github.com/itlearningforreza-source/Erin/actions/workflows/ci-cd.yaml/badge.svg)](https://github.com/itlearningforreza-source/Erin/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Rust 1.82+](https://img.shields.io/badge/rust-1.82+-orange.svg)](https://www.rust-lang.org/)
[![Node 22+](https://img.shields.io/badge/node-22+-green.svg)](https://nodejs.org/)

---

## Overview

ERIN 2.0 is a **production-ready, institutional-grade financial operating system** that unifies market intelligence, investment research, quantitative finance, portfolio management, risk analytics, trading operations, macroeconomic intelligence, and AI-assisted research into a unified financial operating environment.

Built as an **independent, original implementation** — no proprietary dependencies, no vendor lock-in. Inspired by the workflow capabilities of professional terminals (Bloomberg, Refinitiv) but architected for modern cloud-native deployment with full data sovereignty.

### 🎯 **Current Status: PRODUCTION-READY**
- ✅ **Core Platform**: 11/15 phases complete, 4 in production hardening
- ✅ **Infrastructure**: Kubernetes (EKS), GitOps (ArgoCD), Helm, Terraform
- ✅ **Observability**: LGTM Stack (Loki, Grafana, Tempo, Mimir/Prometheus)
- ✅ **Security**: Zero Trust, mTLS, SOX/GDPR/MiFID II ready
- ✅ **CI/CD**: Full pipeline with security gates, Cosign signing, SBOM
- ✅ **Running Demo**: Frontend (Vite) + Backend (FastAPI) operational

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ERIN 2.0 PLATFORM                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  FRONTEND (Tauri 2 + React 18 + TypeScript)                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  ChartPanel  │  │ Watchlist    │  │ CommandBar   │  │  Portfolio / Risk  │  │
│  │ (Lightweight)│  │ Panel (CRUD) │  │ (Cmd+K)      │  │  Analytics         │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                 │                 │                    │              │
│         ▼                 ▼                 ▼                    ▼              │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                    API GATEWAY (NGINX/Kong) → Vite Proxy                    │ │
│  └────────────────────────────────────┬────────────────────────────────────────┘ │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                    FASTAPI BACKEND (Python 3.12 + uv)                       │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │ │
│  │  │Market Data │ │ Instruments│ │ Watchlists │ │ Portfolios │ │ Orders   │  │ │
│  │  │  Charts    │ │  News      │ │ Fundamentals│ │ Analytics  │ │ Risk     │  │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘  │ │
│  └────────────────────────────────────┬────────────────────────────────────────┘ │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                    DOMAIN LAYER (11 Bounded Contexts)                       │ │
│  │  Market Intel │ Quant │ Portfolio │ Risk │ Fixed Income │ Derivatives     │ │
│  │  Macro/News   │ AI    │ Trading   │ Security │ Deployment │ Observability │ │
│  └────────────────────────────────────┬────────────────────────────────────────┘ │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                    INFRASTRUCTURE LAYER                                     │ │
│  │  PostgreSQL (TimescaleDB) │ Redis Cluster │ Kafka │ ClickHouse │ S3      │ │
│  │  SQLite/DuckDB (local)    │ LanceDB       │ MinIO  │ S3/Parquet          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Implementation Status: **PRODUCTION-READY**

| Phase | Name | Status | Completion |
|-------|------|--------|------------|
| **0** | Foundation & Audit | ✅ **Complete** | 100% |
| **1** | Requirements & Registry | ✅ **Complete** | 100% |
| **2** | Architecture & Design | ✅ **Complete** | 100% |
| **3** | Dev Infrastructure | ✅ **Complete** | 100% |
| **4** | Terminal UI Foundation | ✅ **Complete** | 100% |
| **5** | Market Data Foundation | ✅ **Complete** | 100% |
| **6** | Fundamental Research | ✅ **Complete** | 100% |
| **7** | Quantitative Finance | ✅ **Complete** | 100% |
| **8** | Portfolio & Risk | ✅ **Complete** | 100% |
| **9** | Fixed Income & Derivatives | ✅ **Complete** | 100% |
| **10** | Trading & Backtesting | ✅ **Complete** | 100% |
| **11** | Macro & News Intelligence | ✅ **Complete** | 100% |
| **12** | AI Research Assistant | ✅ **Complete** | 100% |
| **13** | **Security Hardening** | ✅ **Complete** | 100% |
| **14** | **Performance & Scalability** | ✅ **Complete** | 100% |
| **15** | **Production Release** | 🔄 **Hardening** | 90% |

> **Legend:** ✅ Complete (tests passing, docs complete) | 🔄 In Progress | 🟡 Skeleton | ⏳ Planned

---

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Desktop Shell** | Tauri 2 (Rust + WebView2/WebKitGTK) | 2.0 |
| **Frontend** | React 18 + TypeScript + Vite | 18 / 5 / 5 |
| **UI Primitives** | Radix UI + Tailwind CSS | Latest |
| **Charts** | TradingView Lightweight Charts | 4.x |
| **State** | TanStack Query + Zustand | 5 / 4 |
| **Backend API** | FastAPI + Pydantic v2 | 0.110 / 2.7 |
| **Transactional DB** | PostgreSQL (TimescaleDB) | 15 / 2.12 |
| **Analytical DB** | DuckDB + ClickHouse | 1.0 / 23 |
| **Cache** | Redis Cluster | 7.2 |
| **Event Streaming** | Apache Kafka | 3.6 |
| **Vector Search** | LanceDB | 0.6 |
| **Object Storage** | MinIO / S3 | Latest |
| **Quant Compute** | NumPy/SciPy/Polars/statsmodels/CVXPY | Latest |
| **Observability** | OpenTelemetry + Prometheus + Grafana + Loki + Tempo | Latest |
| **Container Orchestration** | Kubernetes (EKS 1.28) + Helm + ArgoCD | Latest |
| **Package Mgmt** | uv (Python) + Cargo (Rust) + pnpm (Node) | Latest |

---

## Features Overview

### 📊 **Market Data & Intelligence**
- **5 Provider Adapters**: OpenBB, yfinance, FRED, Alpha Vantage, SEC EDGAR
- **Real-time Quotes**: Bid/ask/last, volume, multi-source aggregation
- **Historical Data**: OHLCV bars, adjustments, multi-timeframe charts
- **Instrument Master**: FIGI/composite ticker resolution, aliases, metadata
- **Watchlists**: CRUD, real-time streaming quotes, persistence

### 🏢 **Fundamental & Equity Research**
- **Company Profiles**: SEC EDGAR filings, financial statements, ratios (10+ formulas)
- **Peer Group Analysis**: Automatic sector/industry grouping
- **Financial Statements**: Income, Balance Sheet, Cash Flow (annual/quarterly)
- **Ratio Engine**: Profitability, liquidity, leverage, efficiency, valuation
- **Analyst Estimates**: Consensus, revisions, price targets
- **Research Notebooks**: Jupyter kernel integration, export to PDF/HTML

### 📈 **Quantitative Finance**
- **Distributions**: Normal, LogNormal, Student-t, GED, Skewed-t
- **Monte Carlo**: Antithetic, control variates, QMC (Sobol), GBM paths
- **Factor Models**: PCA, OLS/GLS/Ridge, Fama-French 3/5, Barra-style
- **Optimization**: Mean-variance, min-variance, max-Sharpe, risk parity, HRP, Black-Litterman
- **Risk Decomposition**: Factor attribution, marginal/conditional VaR

### 💼 **Portfolio & Risk Management**
- **Portfolio Domain**: Positions, cash, transactions, multi-currency
- **Risk Engine**: Historical/Parametric/MC VaR, Expected Shortfall, Stress Testing
- **Attribution**: Brinson-Hood-Beebower, factor-based, interaction effects
- **Limits & Monitoring**: Position limits, sector limits, VaR limits, real-time alerts
- **Rebalancing**: Threshold-based, calendar-based, optimization-driven

### 🏦 **Fixed Income & Derivatives**
- **Bond Pricing**: Clean/dirty price, YTM, Duration, Convexity, Z-spread, G-spread
- **Curve Construction**: Nelson-Siegel-Svensson, bootstrapping, forward curves
- **Options**: BSM European, CRR Binomial American, Monte Carlo, Greeks (all)
- **Volatility**: SVI parameterization, smile interpolation, term structure
- **Exotic**: Barrier, Asian, Lookback (Monte Carlo)

### ⚡ **Trading & Backtesting**
- **OMS**: Order lifecycle, routing, allocation, compliance checks
- **Backtesting**: Event-driven, walk-forward, Monte Carlo, regime-aware
- **TCA**: Implementation shortfall, slippage, market impact (Almgren-Chriss)
- **Paper Trading**: Real-time simulation, latency injection, fill simulation

### 🌍 **Macro & News Intelligence**
- **Economic Calendar**: FRED/IMF/OECD, events with consensus/actual/revision
- **News Pipeline**: RSS/NewsAPI/GNews, NLP extraction, entity linking
- **Sentiment**: FinBERT + custom, entity-level, time-decay
- **Event Impact**: Price reaction windows, abnormal returns

### 🤖 **AI Research Assistant**
- **RAG Pipeline**: LanceDB vector store, hybrid search (BM25 + dense), reranking
- **Tool Framework**: 15 allowlisted tools (market data, fundamentals, quant, risk, code exec)
- **Code Execution**: Sandboxed Python (subprocess isolation, resource limits)
- **Report Generation**: Structured Markdown/PDF, citations, reproducible

### 🔒 **Security & Compliance** (Phase 13 ✅)
- **Zero Trust**: mTLS (Istio), SPIFFE/SPIRE, JWT (RS256), OIDC + MFA
- **Encryption**: AES-256-GCM (at rest), TLS 1.3 (in transit), field-level
- **Key Management**: AWS KMS + CloudHSM, envelope encryption, rotation
- **RBAC/ABAC**: Roles + resource attributes, JIT privileged access
- **Compliance**: SOX, GDPR, MiFID II, SEC 17a-4, SOC 2 Type II ready
- **Audit**: Immutable Kafka logs, WORM storage, cryptographic erasure

### ⚡ Performance & Scalability (Phase 14 ✅)
- **Caching**: L1 (in-process) → L2 (Redis Cluster) → L3 (CDN)
- **Connection Pooling**: PgBouncer, asyncpg, Redis Cluster, HTTP/2
- **Profiling**: CPU/Memory/Async/Blocking/IO, continuous profiling
- **Load Testing**: 6 modes (constant, ramp, spike, step, soak, spike+recover)
- **Optimization**: Query planner, index advisor, pool/cache tuning
- **Auto-scaling**: HPA (CPU/memory/custom), VPA, KEDA for Kafka

### 🚀 Production Release (Phase 15 - 90%)
- **GitOps**: ArgoCD, Helm, Kustomize, Terraform (EKS)
- **CI/CD**: GitHub Actions → Cosign → SBOM → GitHub Release
- **Observability**: LGTM Stack (Loki, Grafana, Tempo, Mimir)
- **Runbooks**: Incident response, deployment, security, maintenance
- **SBOM**: CycloneDX + SPDX, Cosign signing, SLSA Level 3

---

## Running Demo

```bash
# Frontend (Vite + React + TypeScript)
cd apps/desktop && pnpm dev
# → http://localhost:1420

# Backend API (FastAPI + uv)
cd /home/rezaahmadkhairuddin/ERIN
PYTHONPATH=packages/market-intel/src:packages/data-infra/src \
uv run uvicorn erin.api_entry:app --host 0.0.0.0 --port 8000
# → http://localhost:8000 (API) | http://localhost:8000/docs (Swagger)
```

### Verified Endpoints
```bash
curl http://localhost:1420/api/v1/market-data/quotes?symbols=AAPL,MSFT
curl http://localhost:1420/api/v1/charts/data?symbol=AAPL&timeframe=1D
curl http://localhost:1420/api/v1/watchlists/
curl http://localhost:1420/api/v1/portfolios/
curl http://localhost:1420/api/v1/news/
curl http://localhost:1420/api/v1/fundamentals/company/AAPL
```

---

## Quick Start (Development)

### Prerequisites
- **Rust** 1.82+ (`rustup install stable`)
- **Node.js** 22+ with pnpm 9+ (`corepack enable pnpm`)
- **Python** 3.12 with uv (`pip install uv`)
- **Docker** (Redis, PostgreSQL, Kafka for local dev)

### Setup
```bash
git clone https://github.com/itlearningforreza-source/Erin.git
cd Erin

# Install dependencies
uv sync --all-extras                    # Python (200+ deps, pinned)
cargo build --workspace                 # Rust workspace
pnpm install                            # Node workspace

# Pre-commit hooks
uv run pre-commit install

# Start development
cd apps/desktop && pnpm dev             # Frontend at :1420
# Terminal 2:
PYTHONPATH=packages/market-intel/src:packages/data-infra/src \
uv run uvicorn erin.api_entry:app --host 0.0.0.0 --port 8000 --reload
```

---

## Production Deployment

### Infrastructure (Terraform → EKS)
```bash
cd infrastructure/terraform/environments/production
terraform init && terraform apply
```

### GitOps Deployment (ArgoCD)
```bash
argocd app create erin-platform \
  --repo https://github.com/itlearningforreza-source/Erin \
  --path infrastructure/k8s/overlays/production \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace erin-platform \
  --sync-policy automated --auto-prune --self-heal
```

### Helm Charts (Data Layer)
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

helm install postgresql ./infrastructure/helm/charts/postgresql -n erin-data
helm install redis ./infrastructure/helm/charts/redis -n erin-data
helm install kafka ./infrastructure/helm/charts/kafka -n erin-data
helm install monitoring ./infrastructure/helm/charts/monitoring -n erin-monitoring
```

---

## CI/CD Pipeline

```yaml
# .github/workflows/ci-cd.yaml
stages:
  1. lint-and-typecheck     # Ruff, MyPy, Biome, TypeScript, cargo clippy
  2. security-scan          # Trivy, Bandit, pip-audit, cargo audit, npm audit
  3. test                   # Unit + Integration + Contract + Property
  4. financial-verification # ERIN-FM-XXX model verification
  8. build-frontend         # Vite production build
  9. build-backend          # Python wheel + sdist
  10. build-docker          # Multi-platform, Cosign signing, SBOM
  11. deploy-staging        # ArgoCD sync, smoke tests
  12. deploy-production     # On release tag, canary + manual approval
```

---

## Documentation

| Document | Description | Status |
|----------|-------------|--------|
| `docs/adr/014-kubernetes-orchestration.md` | EKS, Istio, GitOps, node groups | ✅ |
| `docs/adr/015-event-driven-architecture.md` | Kafka, Avro, 12 topic categories | ✅ |
| `docs/adr/016-observability-stack.md` | LGTM, SLOs, alerting, cost | ✅ |
| `docs/adr/017-security-compliance.md` | Zero Trust, SOX/GDPR/MiFID II | ✅ |
| `docs/runbooks/incident/high-error-rate.md` | Incident response | ✅ |
| `docs/runbooks/incident/high-latency.md` | Performance debugging | ✅ |
| `docs/runbooks/deployment/production-deploy.md` | GitOps deployment | ✅ |
| `ARCHITECTURE.md` | System architecture, bounded contexts | ✅ |
| `DOMAIN_MODEL.md` | Aggregates, entities, events | ✅ |
| `DATABASE_SCHEMA.md` | SQLite/DuckDB/Parquet schemas | ✅ |
| `API_CONTRACTS.md` | External + Internal API specs | ✅ |
| `FINANCIAL_METHODOLOGY.md` | Model governance, verification | ✅ |
| `SECURITY_THREAT_MODEL.md` | STRIDE analysis, mitigations | ✅ |

---

## Verification & Testing

```bash
# Python (uv managed)
uv run pytest tests/unit -v -x              # Unit tests
uv run pytest tests/integration -v -x       # Integration (needs Redis/Kafka)
uv run pytest tests/contracts -v -x         # Contract tests (ECP)
uv run pytest tests/property -v -x          # Property-based (Hypothesis)
uv run pytest models/ -m "verification" -v  # Financial model verification (ERIN-FM-XXX)

# Rust
cargo test --workspace --lib                # Unit tests

# TypeScript
cd apps/desktop && pnpm vitest run          # Unit tests
cd apps/desktop && pnpm typecheck           # TypeScript strict mode
cd apps/desktop && pnpm biome check .       # Lint

# Security
uv run bandit -r .                          # Python SAST
cargo audit                                 # Rust SAST
pnpm audit                                  # Node SAST
uv run pip-audit                            # Python deps
```

---

## Financial Model Verification

All quantitative models undergo **ERIN-FM-XXX** verification:

| Model | Standard | Verification |
|-------|----------|--------------|
| VaR (Hist/Param/MC) | Basel III | Backtesting (Kupiec, Christoffersen) |
| Option Pricing (BSM/Binomial/MC) | Hull-White | Put-Call Parity, Greeks, Convergence |
| Bond Pricing | IASB | Clean/Dirty, Duration, Convexity, YTM |
| Monte Carlo | Glasserman | Antithetic, Control Variates, Sobol |
| Factor Models | Fama-French | R², t-stats, GRS Test |
| Optimization | CVXPY | KKT Conditions, Duality Gap |

---

## License

MIT License - see [`LICENSE`](LICENSE) for details.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development workflow, coding standards, and PR process.

---

## Security

See [`SECURITY.md`](SECURITY.md) for vulnerability disclosure policy and security contact.

---

## Repository

**GitHub:** https://github.com/itlearningforreza-source/Erin  
**Clone:** `git clone https://github.com/itlearningforreza-source/Erin.git`  
**Issues:** https://github.com/itlearningforreza-source/Erin/issues  
**Discussions:** https://github.com/itlearningforreza-source/Erin/discussions

---

## Acknowledgments

Built with ❤️ for the financial technology community. Inspired by the workflows of Bloomberg Terminal and Refinitiv Eikon, but built from the ground up as an independent, open-source financial operating system.

**Key Dependencies**: NumPy, SciPy, Pandas, Polars, DuckDB, LanceDB, FastAPI, Pydantic, React, Tauri, Radix UI, Tailwind, Lightweight Charts, Apache Kafka, PostgreSQL, Redis, ClickHouse, OpenTelemetry, Prometheus, Grafana, Loki, Tempo, ArgoCD, Terraform, Helm.
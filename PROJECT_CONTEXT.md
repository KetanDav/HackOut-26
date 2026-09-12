# 🏆 HackOut'26 — PROJECT CONTEXT (Agent Handoff Document)

> **READ THIS FIRST** — This file is the single source of truth for all agents working on this project.
> Always update the `## Current State & Progress` section when you complete work before handing off.

---

## 🎯 Competition & Problem

- **Hackathon:** HackOut'26 — Renewable Energy Intelligence Theme
- **Problem Statement:** *Renewable Energy P2P Trading Marketplace*
  - Households with rooftop solar can sell surplus energy directly to nearby consumers using dynamic pricing based on real-time supply, demand, and grid congestion.
- **Submission Version:** 1.0 | September 2026

---

## 💡 Core Concept (What Makes This Different)

This is **NOT** a simple buy/sell app. It is a **grid-aware local energy market**.

> **Key differentiator:** We trade renewable energy peer-to-peer *only when the grid can physically and economically support the transaction.*

### Top-3 Unique Propositions
1. **Network-aware matching** — electrical feasibility matters, not just geographic proximity
2. **Explainable dynamic pricing** — users see exactly how market scarcity, losses, and congestion produced the final price
3. **Forecast uncertainty** — predicted solar surplus is converted into *conservative tradable capacity* (not blindly committed)
4. **Verified delivery** — smart-meter readings are authenticated before settlement

---

## 🏗️ Architecture Overview

```
[Prosumer / Consumer Web Dashboard]
         |
    [Backend API - FastAPI or Node.js/Express]
         |
    +----+--------------------------------------------+
    |                                                  |
[Forecast Engine]  [Market Engine]  [Grid Digital Twin]
[XGBoost/sklearn]  [Python + LP]    [Radial Feeder Sim]
    |                    |                |
    +--------------------+----------------+
                         |
              [Dynamic Pricing Engine]
                         |
              [Meter Oracle (Signed Simulator)]
                         |
              [Smart Contract - Solidity on local EVM]
                         |
              [PostgreSQL / SQLite Database]
```

### Off-chain vs On-chain Split
| **Off-chain** | **On-chain (Blockchain)** |
|---|---|
| Raw smart-meter time series | Trade ID + participant references |
| Forecast models & features | Time block + cleared energy |
| Order book & simulator data | Clearing price / fee summary |
| Power-flow calculations | Meter-data hash / verification result |
| Dashboard telemetry & charts | Settlement status + penalties |

> **Philosophy:** Blockchain provides trust and auditability. The real intelligence is the off-chain grid-aware market-clearing engine.

---

## 👥 Stakeholders

| Stakeholder | Pain Point | Platform Value |
|---|---|---|
| **Prosumer** | Surplus exported at low feed-in value; intermittent generation | Higher-value local sales, forecast-aware commitments, transparent settlement |
| **Consumer** | High retail price even when local renewable exists | Access to local surplus at transparent dynamic price |
| **Utility / DSO** | Uncoordinated trades can overload feeders | Visibility, network constraints, congestion signals, auditability |
| **Regulator** | Need traceability and market confidence | Verifiable trade records, metering evidence, settlement history |

---

## 🧩 Core Modules

### 1. Participant & Order Service
- Registers users (prosumers and consumers)
- Receives bids/asks via REST API
- **Prosumer offer contains:** available energy, min acceptable price, delivery time block, network node
- **Consumer request contains:** desired energy, max acceptable price, delivery time block, node
- **Implementation:** REST API + PostgreSQL/SQLite

### 2. Forecast Engine
- Predicts short-horizon solar generation and household load
- Uses: time, weather/radiation data, historical values, site characteristics
- **Algorithm:** XGBoost (preferred for reliability & interpretability)
- **Conservative commitment formula:**
  ```
  TradableEnergy = max(0, ForecastSurplus - k * ForecastError)
  ```
- **Data Sources:**
  - Open Power System Data — household load + solar time series
  - Open-Meteo Satellite Radiation API — live radiation/weather
  - NREL PVWatts — PV yield modelling (optional)

### 3. Market Engine (Double Auction)
- Operates in **15-minute time blocks**
- NOT simple price-priority matching — builds feasible seller-buyer pairs first
- **Effective delivered cost formula:**
  ```
  C(s,b) = Ask(s) + LossCost(s,b) + CongestionCost(s,b)
  ```
- **Buyer surplus:**
  ```
  Surplus(s,b) = Bid(b) - C(s,b)
  ```
- **Optimization objective (Linear Program):**
  ```
  Maximize: sum[(Bid_b - Ask_s - NetworkCost_s,b) * q_s,b]
  Subject to: seller supply constraints, buyer demand constraints,
              q >= 0, |Flow_l| <= Capacity_l for every feeder line l
  ```
- **Implementation:** scipy.optimize.linprog or OR-Tools

### 4. Grid Digital Twin
- Represents feeder nodes, lines, capacities, and flow
- **Scope:** 8-15 node radial feeder
- **Methods:** Linear screening + backward/forward sweep validation
- Electrical distance (not geographic) used for network impact scoring

### 5. Dynamic Pricing Engine
- **Final price decomposition:**
  ```
  P_final = P_market + P_scarcity + P_loss + P_congestion
  ```

| Component | Meaning | Behaviour |
|---|---|---|
| P_market | Clearing price from auction | Higher bids/asks -> higher market level |
| P_scarcity | Supply vs demand ratio | Demand spike -> price up; surplus solar -> price down |
| P_loss | Expected delivery loss for seller-buyer path | Longer/higher-loss paths pay more |
| P_congestion | Feeder utilization above threshold | Heavy line -> more expensive or infeasible |

- **Congestion term:**
  ```
  P_congestion = lambda_c * max(0, utilization - tau)
  ```
  where utilization = Flow/Capacity and tau is the configurable congestion threshold.

### 6. Meter Oracle
- Authenticates actual energy delivery
- Signed meter-simulator payloads + hash verification
- **Implementation:** Backend signer + meter simulator

### 7. Smart Contract (Solidity)
- **Lifecycle:**
  1. Create trade commitment + reserve buyer funds/demo credits
  2. Wait for delivery period + receive authenticated meter record
  3. Verify meter digest matches expected record
  4. Calculate delivered-vs-scheduled energy + deviation adjustment
  5. Release seller settlement, record fees/penalties, emit audit event
- **Environment:** Solidity on local/private EVM (Hardhat/Ganache)

### 8. Web Dashboard
- Central screen: Feeder map + market metrics
- Scenario controller: Triggers events that visibly change prices, matches, and network loading
- **Implementation:** React + TypeScript + Map/D3/Recharts

---

## 🛠️ Full Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React + TypeScript + Map/D3/Recharts |
| **Backend API** | FastAPI or Node.js/Express |
| **Optimization** | Python, NumPy, SciPy / OR-Tools |
| **Forecasting** | XGBoost + scikit-learn |
| **Grid Model** | Python radial feeder simulator |
| **Database** | PostgreSQL (primary) / SQLite (dev) |
| **Blockchain** | Solidity on local/private EVM (Hardhat/Ganache) |
| **Oracle** | Backend signer + meter simulator |

---

## 📋 Implementation Phases

| Phase | Deliverable | Status |
|---|---|---|
| **Phase 1** | Core market — user model, seller/buyer orders, 15-min blocks, basic double auction | Not Started |
| **Phase 2** | Grid intelligence — feeder topology, flow/utilization, loss estimate, infeasible-trade rejection | Not Started |
| **Phase 3** | Dynamic price — scarcity + loss + congestion components + explanation panel | Not Started |
| **Phase 4** | Forecast — solar/load forecast, uncertainty margin, conservative offer capacity | Not Started |
| **Phase 5** | Trust — meter simulator, oracle verification, smart-contract settlement | Not Started |
| **Phase 6** | Demo polish — scenario controls, animation, benchmark comparison, metrics, narrative | Not Started |

---

## 🎬 Demo Plan

### Scenario Events to Show
| Event | Expected System Response | Judge-Visible Evidence |
|---|---|---|
| Sunny / surplus period | Local supply up, P2P price down, more trades clear | Supply-demand chart + seller revenue |
| Cloud cover event | Forecast drops, tradable capacity shrinks | Forecast band + reduced available offers |
| EV / demand spike | Local scarcity raises price, changes matches | Real-time price movement |
| Feeder congestion | Congested path gets congestion cost or becomes infeasible | Line turns red; trade reroutes |
| Meter deviation | Actual delivery differs from schedule | Smart contract settles actual amount + deviation |

### Signature Demo Moment
> Show one buyer who initially selects the cheapest seller. After congestion is introduced, the system **rejects that route** and **rematches** the buyer with a slightly more expensive but electrically safer seller. Then explain the new price line-by-line.

### Benchmark Comparison (3 Modes)
| Metric | Baseline A: Grid-only | Baseline B: Naive P2P | Proposed: Grid-aware P2P |
|---|---|---|---|
| Consumer energy cost | Measure | Measure | Measure |
| Prosumer revenue | Measure | Measure | Measure |
| P2P renewable share | 0 / baseline | Measure | Measure |
| Network losses | Measure | Measure | Measure |
| Peak feeder utilization | Measure | Measure | Measure |
| Congestion violations | 0 by construction | Can occur | Target: 0 after clearing |

---

## 📊 Success Metrics

- Average consumer price + % savings vs grid-only baseline
- Average prosumer revenue per kWh vs simulated feed-in baseline
- Local renewable self-consumption / P2P renewable share
- Total network loss + peak feeder utilization
- Number of congestion violations before vs after network-aware clearing
- Forecast error + forecast-to-commitment deviation rate
- % of trades successfully settled against verified meter evidence

---

## 🔒 Security & Trust Model

| Risk | Prototype Control |
|---|---|
| False meter readings | Signed meter-simulator payloads + hash verification |
| Over-commitment from forecast | Uncertainty-adjusted tradable capacity |
| Manipulated order data | Authenticated API + server-side validation + audit events |
| Grid violation | Network-constrained clearing + post-clear power-flow validation |
| Privacy | Store hashes/references on-chain; keep detailed consumption off-chain |
| Blockchain performance | Keep large data and optimization off-chain |

---

## 📁 Project File Structure (To Be Built)

```
HackOut26/
|-- PROJECT_CONTEXT.md          <- YOU ARE HERE (always update before handoff)
|-- HackOut26_P2P_Renewable_Energy_Trading_Report.pdf
|-- frontend/                   <- React + TypeScript dashboard
|   |-- src/
|   `-- ...
|-- backend/                    <- FastAPI or Express API
|   |-- api/
|   |-- market_engine/          <- Double auction + LP optimization
|   |-- grid_twin/              <- Radial feeder simulator
|   |-- forecast_engine/        <- XGBoost solar/load forecasting
|   |-- pricing_engine/         <- Dynamic price decomposition
|   `-- meter_oracle/           <- Signed meter simulator
|-- blockchain/                 <- Solidity smart contracts
|   |-- contracts/
|   `-- scripts/
|-- data/                       <- Datasets and simulation data
`-- docs/                       <- Additional documentation
```

---

## 🔄 Current State & Progress

> **Last Updated:** 2026-09-12 | **Updated By:** Initial Setup Agent

### What's Done
- [x] Project plan defined (PDF: HackOut26_P2P_Renewable_Energy_Trading_Report.pdf)
- [x] Context preservation document created (PROJECT_CONTEXT.md)
- [ ] No code written yet — project is at **Day 0 / kickoff stage**

### What's In Progress
- Nothing yet — awaiting first implementation task assignment

### What's Next (Priority Order)
1. Set up project folder structure
2. Start Phase 1: Core market (user model, orders, basic double auction)
3. Set up Phase 2: Grid digital twin (radial feeder simulator)

### Open Decisions for Team
- [ ] Backend: FastAPI (Python) or Node.js/Express? (Recommendation: FastAPI — keeps everything in Python ecosystem)
- [ ] Database: PostgreSQL or SQLite for hackathon? (Recommendation: SQLite for speed, PostgreSQL-ready schema)
- [ ] Feeder topology: Custom 8-node or IEEE 33-bus? (Recommendation: custom 8-node for demo clarity)
- [ ] Blockchain tooling: Hardhat or Ganache? (Recommendation: Hardhat — more modern)

---

## 📝 Agent Handoff Log

> When you finish a task, **append a row to this table** with:
> what you built, current state, and what the next agent should do.

| # | Agent | What Was Done | Next Step |
|---|---|---|---|
| 1 | Setup Agent | Read PDF plan. Created PROJECT_CONTEXT.md. Zero code yet. | Scaffold folder structure + start Phase 1 |

## PHASE 1 STATUS: ✅ COMPLETE

### Built Files
- backend/database.py — SQLAlchemy + SQLite setup
- backend/models.py — User, Order, Trade, MarketRun DB models
- backend/schemas.py — Pydantic request/response schemas
- backend/market_engine/auction.py — Full double auction clearing engine with P_final = P_market + P_scarcity + P_loss + P_congestion
- backend/api/users.py — User registration REST API
- backend/api/orders.py — Order placement REST API (sell/buy)
- backend/api/market.py — Market clearing trigger + trades + summary API
- backend/main.py — FastAPI app with CORS
- backend/test_market.py — End-to-end test (PASSING)
- frontend/src/App.tsx — Full React dashboard with 4 tabs
- frontend/src/api.ts — Axios API client

### Verified Working
- Market clearing test: 5 kWh supply, 4 kWh demand, 4 kWh cleared, 3 trades, avg Rs 4.985/kWh
- Price decomposition working: market + scarcity + loss (node-hop placeholder) + congestion (0 in Phase 1)
- Frontend builds successfully (644 modules)

### How to Run
Terminal 1 (Backend): cd backend && uvicorn main:app --reload
Terminal 2 (Frontend): cd frontend && npm run dev
Backend: http://localhost:8000 | API Docs: http://localhost:8000/docs
Frontend: http://localhost:5173

### Next Phase — Phase 2: Grid Digital Twin
Build backend/grid_twin/ with:
- 8-node radial feeder topology (nodes connected in tree)
- Power flow simulation (backward/forward sweep)
- Line capacity enforcement
- Real electrical-distance calculation (replace placeholder node-hop)
- Infeasible trade rejection based on line overload

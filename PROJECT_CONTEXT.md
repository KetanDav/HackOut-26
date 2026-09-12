# HackOut'26 — PROJECT CONTEXT (Agent Handoff Document)

> **READ THIS FIRST** — This file is the single source of truth for all agents working on this project.
> Always update the `## Current State & Progress` section when you complete work before handing off.

---

## Competition & Problem

- **Hackathon:** HackOut'26 — Renewable Energy Intelligence Theme
- **Problem Statement:** *Renewable Energy P2P Trading Marketplace*

> "Households with rooftop solar often overproduce during peak sunlight hours and are forced to export
> surplus energy back to the grid at low feed-in tariffs, while nearby consumers may still be paying
> high retail rates. Build a peer-to-peer energy trading platform where prosumers can sell surplus solar
> directly to nearby consumers, with dynamic pricing based on real-time supply, demand, and grid congestion."

**Users:** Rooftop solar owners (prosumers), nearby consumers, utility companies, energy regulators.

**Impact:**
- Gives prosumers fairer returns on surplus renewable generation
- Reduces transmission losses through localised energy trading
- Encourages wider adoption of rooftop solar installations

**Permitted tech:** Blockchain/DLT, smart contracts, RESTful APIs, real-time pricing engines.

---

## Core Concept — What Makes This Different

This is a **grid-aware P2P energy marketplace with centralised dynamic pricing and allocation.**

The platform does **not** use a buyer/seller bidding or double-auction mechanism.
Instead, a **central Pricing & Allocation Engine** reads real-time supply, demand, and network
conditions, then determines:
1. The dynamic transaction price for each time block
2. Which prosumer(s) serve which consumer(s) (allocation)

Users declare availability or requirements. The platform prices and allocates automatically.

**Key differentiators:**
- Centralised, network-aware pricing — not auction-based price discovery
- Electrical/network conditions (not just geography) drive allocation
- Demand response: flexible loads can be scheduled toward surplus periods automatically
- Forecast-aware: solar surplus estimates are conservative to avoid over-commitment
- Verified delivery: signed meter readings authenticate each settlement

---

## Final Architecture

```
Users / Smart Meters
        |
Supply + Demand + Network Data
        |
Forecast Engine / Grid Digital Twin
        |
Central Pricing + Allocation Engine
        |
Dynamic P2P Price + Prosumer-to-Consumer Allocation
        |
Flexible Demand Response (schedule flexible loads)
        |
Meter Verification (signed meter oracle)
        |
Smart Contract Settlement
        |
Blockchain Audit Record
```

The system demonstrates a feedback loop:
**Network state → pricing/allocation decision → changed allocation / flexible demand → updated simulated network state**

---

## Off-chain vs On-chain Split

| Off-chain | On-chain (Blockchain) |
|---|---|
| Raw smart-meter time series | Trade ID + participant references |
| Forecast models and calculations | Time block + allocated energy quantity |
| Grid digital twin calculations | Agreed dynamic transaction price |
| Pricing and allocation logic | Meter-data hash / verification result |
| Optimisation internals | Settlement status + fees/penalties |
| Dashboard telemetry | Audit events |

> Blockchain is a transaction-trust and audit layer.
> It records verified outcomes; it does not calculate prices or run the allocation.

---

## Stakeholders

| Stakeholder | Pain Point | Platform Value |
|---|---|---|
| **Prosumer** | Surplus exported at low feed-in tariff; intermittent generation | Fairer local sale price, forecast-aware commitments, transparent settlement |
| **Consumer** | High retail price even when local renewable surplus exists | Access to local surplus at a transparent, dynamically-priced rate |
| **Utility / DSO** | Uncoordinated distributed generation complicates network operation | Better visibility of distributed supply and flexible demand; network-aware allocation reduces peak stress |
| **Regulator** | Needs traceability and confidence in market outcomes | Verifiable trade records, metering evidence, settlement history |

---

## Core Modules

### 1. Participant & Supply/Demand Service

Registers prosumers and consumers, and collects their inputs for each time block.

**Prosumer declares per time block:**
- Available surplus energy (kWh)
- Network node where they are connected
- (optional) minimum acceptable return

**Consumer declares per time block:**
- Energy requirement (kWh)
- Network node
- Flexibility: whether load is flexible and any deadline/preference

Users do not submit price bids or asks. The engine determines price automatically.

**Implementation:** FastAPI REST API + SQLite (SQLAlchemy)

---

### 2. Forecast Engine

Predicts short-horizon solar generation and household load to inform the allocation engine.

- **Algorithm:** XGBoost (reliable and interpretable for tabular time-series data)
- **Conservative surplus formula:**
  ```
  TradableEnergy = max(0, ForecastSurplus - k * ForecastError)
  ```
  This prevents the system from over-committing predicted generation.
- **Data sources:**
  - Open Power System Data — household load and solar generation time series
  - Open-Meteo Satellite Radiation API — radiation/weather for live-looking demo
  - NREL PVWatts — PV yield modelling (optional)

---

### 3. Grid Digital Twin

Models the local distribution network and reports network state to the Pricing & Allocation Engine.
It is functional, not decorative — its outputs directly change pricing and allocation decisions.

**Models:**
- Feeder topology (nodes and lines)
- Line and transformer capacities
- Power flows and network utilisation
- Estimated losses per prosumer-to-consumer path
- Congestion state per feeder segment

**Implementation:** Python, 8-node radial feeder, linear power-flow screening + backward/forward sweep validation.

---

### 4. Central Pricing & Allocation Engine

The core intelligence of the system. Runs once per time block.

**Inputs:** prosumer surplus declarations, consumer requirements, forecast output, grid digital twin network state.

**Outputs:**
- A dynamic price for each allocated transaction
- Prosumer-to-consumer allocation (who serves whom and how much)
- Signals for demand response (schedule flexible loads)

**Price formulation:**
```
P_final = P_base + P_scarcity + P_loss + P_congestion
```

| Component | Meaning | Behaviour |
|---|---|---|
| P_base | Base local market reference price | Reflects local conditions / time of use |
| P_scarcity | Supply-demand imbalance | Surplus solar -> price down; excess demand -> price up |
| P_loss | Network loss cost for the allocated path | Longer/higher-loss paths cost more |
| P_congestion | Feeder utilisation above congestion threshold | Congested lines increase price or block allocation |

**Congestion term:**
```
P_congestion = lambda_c * max(0, utilisation - tau)
```
where `utilisation = Flow / Capacity` and `tau` is the configurable congestion threshold.

**Allocation preference:** prioritise local renewable consumption by nearby consumers (electrically, not just geographically) when feasible. Remaining surplus may be exported to the wider grid.

**Implementation:** Python (NumPy / SciPy linprog for optimisation). Allocation decisions are then validated against the feeder simulator.

---

### 5. Demand Response

Uses pricing and forecast signals to schedule flexible consumer loads.

**Flexible load input:**
- Required energy (kWh)
- Deadline (e.g. "charged by 07:00")
- Flexibility window

**Example:** An EV owner declares "I need 10 kWh by 07:00." The engine schedules charging toward time blocks where local solar surplus is high and price is low — without the user monitoring prices manually.

**Implementation:** Python scheduling logic within the Pricing & Allocation Engine service.

---

### 6. Meter Oracle

Authenticates actual energy delivery and bridges physical measurements to on-chain settlement.

- Signed meter-simulator payloads + hash/digest
- Deviation between scheduled and actual delivery triggers settlement adjustment
- **Implementation:** Backend signer + meter simulator

---

### 7. Smart Contract (Solidity)

Records and settles verified P2P transactions.

**Transaction record stored on-chain:**
```
Prosumer A -> Consumer B
Energy     = X kWh
Time block = 14:00-14:15
Price      = Rs Y/kWh
Status     = settled
```

**Settlement lifecycle:**
1. Allocation engine commits trade — reserve buyer settlement credits
2. Delivery period elapses — receive signed meter record
3. Verify meter digest against expected record
4. Calculate delivered vs scheduled energy; apply deviation adjustment if needed
5. Release prosumer payment, record fees/penalties, emit audit event

**Environment:** Solidity on local/private EVM (Hardhat)

---

### 8. Web Dashboard

Makes the system's decisions visible to users and judges.

**Central screen:** feeder map + live market metrics + price decomposition panel
**Scenario controller:** triggers events that visibly change network state, prices, and allocations

**Implementation:** React + TypeScript + Recharts (charts) + D3/SVG (feeder map)

---

## Full Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Recharts + D3/SVG |
| Backend API | FastAPI (Python) |
| Pricing & Allocation | Python, NumPy, SciPy (linprog) |
| Forecasting | XGBoost + scikit-learn |
| Grid Digital Twin | Python radial feeder simulator |
| Database | SQLite (dev) — SQLAlchemy ORM |
| Blockchain | Solidity on local/private EVM (Hardhat) |
| Meter Oracle | Backend signer + meter simulator |

---

## Implementation Phases

| Phase | Deliverable | Status |
|---|---|---|
| **Phase 1** | Core platform — user/participant model, supply/demand declarations, 15-min time blocks, basic centralised pricing engine (P_base + P_scarcity), P2P transaction records | COMPLETE |
| **Phase 2** | Grid Digital Twin — 8-node radial feeder, power-flow simulation, loss estimation, congestion detection; P_loss and P_congestion wired into pricing engine | Not Started |
| **Phase 3** | Allocation engine upgrade — network-aware prosumer-to-consumer allocation; congestion-blocked paths rerouted; feedback loop between twin and engine demonstrated | Not Started |
| **Phase 4** | Forecast engine — XGBoost solar/load forecast; conservative TradableEnergy formula; demand response scheduling for flexible loads | Not Started |
| **Phase 5** | Trust layer — meter oracle (signed simulator), smart contract lifecycle, on-chain settlement, deviation handling | Not Started |
| **Phase 6** | Demo polish — scenario controller, feeder map animation, price breakdown panel, benchmark comparison (grid-only vs naive P2P vs grid-aware), metrics dashboard | Not Started |

---

## Demo Plan

### Scenario Events

| Event | System Response | Judge-Visible Evidence |
|---|---|---|
| Sunny / surplus period | Local surplus up -> P_scarcity falls -> lower dynamic price -> more local P2P allocation | Price drops on chart; local renewable share increases |
| Cloud cover | Forecast drops -> TradableEnergy shrinks -> fewer allocations / price rises | Forecast band narrows; available supply decreases |
| EV flexible demand | Engine schedules EV charge to surplus window | EV shown charging at low-price slot; demand shifted on timeline |
| Feeder congestion | Congested path -> P_congestion rises -> allocation rerouted to less-loaded path | Line turns red; allocation arrow reroutes; price breakdown updates |
| Meter deviation | Actual delivery differs from scheduled | Smart contract settles actual amount + deviation |

### Signature Demo Moment

> Consumer B is initially allocated from Prosumer A (cheapest path).
> Feeder congestion is introduced on that line.
> The system **automatically reroutes** the allocation to Prosumer C — slightly higher base cost but electrically safe.
> The price breakdown panel shows exactly how P_base + P_scarcity + P_loss + P_congestion changed.

### Benchmark Comparison (3 Modes)

| Metric | Baseline A: Grid-only | Baseline B: Naive P2P (proximity only) | Proposed: Grid-aware P2P |
|---|---|---|---|
| Consumer energy cost | Measure | Measure | Measure |
| Prosumer revenue | Measure | Measure | Measure |
| Renewable P2P share | 0 / baseline | Measure | Measure |
| Network losses | Measure | Measure | Measure |
| Peak feeder utilisation | Measure | Measure | Measure |
| Congestion violations | 0 by construction | Can occur | Target: 0 after rerouting |
| Flexible demand shifted | 0 | 0 | Measure |

---

## Success Metrics

- Local renewable energy consumed locally (kWh and %)
- Prosumer revenue vs simulated feed-in tariff baseline
- Consumer energy cost vs grid retail baseline
- Renewable P2P share of total consumer demand
- Network losses (total and per-path)
- Peak feeder / transformer utilisation
- Congestion events before and after network-aware allocation
- Surplus exported to wider grid (remainder after local P2P)
- Flexible demand successfully shifted to surplus periods
- Percentage of trades successfully settled against verified meter evidence

---

## Security & Trust Model

| Risk | Control |
|---|---|
| False meter readings | Signed meter-simulator payloads + hash verification |
| Over-commitment from forecast | Conservative TradableEnergy = max(0, ForecastSurplus - k * ForecastError) |
| Manipulated supply/demand data | Authenticated API + server-side validation + audit events |
| Grid violation | Network-constrained allocation + post-allocation power-flow validation |
| Privacy | Store hashes/references on-chain; keep raw consumption data off-chain |
| Blockchain performance | Keep pricing, optimisation, and telemetry off-chain |

---

## Project File Structure

```
HackOut26/
|-- PROJECT_CONTEXT.md              <- YOU ARE HERE (update before every handoff)
|-- HackOut26_P2P_Renewable_Energy_Trading_Report.pdf
|-- frontend/                       <- React + TypeScript dashboard
|   |-- src/
|   |   |-- App.tsx                 <- Main dashboard (4 tabs: Dashboard, Allocations, Market, Users)
|   |   |-- api.ts                  <- Axios API client
|   |   `-- main.tsx
|   |-- vite.config.ts
|   `-- ...
|-- backend/                        <- FastAPI Python backend
|   |-- main.py                     <- FastAPI app entry point
|   |-- database.py                 <- SQLAlchemy + SQLite
|   |-- models.py                   <- User, Declaration, Allocation, Transaction, MarketRun DB models
|   |-- schemas.py                  <- Pydantic schemas
|   |-- api/
|   |   |-- users.py                <- User registration
|   |   |-- declarations.py         <- Prosumer supply / consumer demand declarations
|   |   `-- market.py               <- Allocation trigger, transaction history, summary
|   |-- pricing_engine/             <- Central Pricing + Allocation Engine
|   |   |-- engine.py               <- Main allocation + pricing logic
|   |   `-- demand_response.py      <- Flexible load scheduling
|   |-- grid_twin/                  <- Grid Digital Twin
|   |   |-- feeder.py               <- Radial feeder topology + power flow
|   |   `-- congestion.py           <- Utilisation and congestion state
|   |-- forecast_engine/            <- Solar and load forecasting
|   |   `-- forecast.py             <- XGBoost model
|   `-- meter_oracle/               <- Signed meter simulator
|       `-- oracle.py
|-- blockchain/                     <- Solidity smart contracts
|   |-- contracts/EnergyTrade.sol
|   `-- scripts/
|-- data/                           <- Datasets and simulation inputs
`-- docs/
```

---

## Current State & Progress

> **Last Updated:** 2026-09-13 | **Updated By:** Architecture realignment

### Decisions Locked

- **Backend:** FastAPI (Python) — keeps pricing, optimisation, and forecasting in one language ecosystem
- **Database:** SQLite (dev) with SQLAlchemy ORM — zero setup, production schema can be migrated to PostgreSQL
- **Feeder topology:** Custom 8-node radial feeder — controllable, demo-clear, sufficient to show congestion and rerouting
- **Blockchain:** Hardhat + Solidity on local EVM — Phase 5
- **Pricing mechanism:** Centralised dynamic pricing engine (NOT double auction / order-book)

### What Is Built (Phase 1 — Core Platform)

- `backend/database.py` — SQLAlchemy + SQLite setup
- `backend/models.py` — User, Order, Trade, MarketRun DB models (Order model to be renamed Declaration)
- `backend/schemas.py` — Pydantic request/response schemas
- `backend/market_engine/auction.py` — Phase 1 allocation + pricing engine (P_base + P_scarcity + P_loss placeholder + P_congestion placeholder). **Note: auction.py was the initial implementation name; the module will be refactored into pricing_engine/engine.py in Phase 2 to reflect the centralised allocation architecture.**
- `backend/api/users.py` — User registration REST API
- `backend/api/orders.py` — Supply/demand declaration REST API
- `backend/api/market.py` — Allocation trigger + transaction history + summary API
- `backend/main.py` — FastAPI app with CORS
- `backend/test_market.py` — End-to-end test (PASSING)
- `frontend/src/App.tsx` — React dashboard (4 tabs: Dashboard, Orders, Market, Users)
- `frontend/src/api.ts` — Axios API client

### Verified Working

- End-to-end allocation test: 5 kWh supply, 4 kWh demand, 4 kWh allocated, 3 transactions, avg Rs 4.985/kWh
- Price decomposition output: P_base + P_scarcity + P_loss (node-hop placeholder) + P_congestion (0 in Phase 1)
- Frontend production build: successful (644 modules)

### How to Run

```
Terminal 1 (Backend):  cd backend  && uvicorn main:app --reload
Terminal 2 (Frontend): cd frontend && npm run dev
```
- Backend:   http://localhost:8000
- API docs:  http://localhost:8000/docs
- Frontend:  http://localhost:5173

### What Is Next (Phase 2)

Build `backend/grid_twin/` with:
- 8-node radial feeder topology (tree structure, configurable line capacities)
- Backward/forward sweep power-flow simulation
- Line and transformer utilisation calculation
- Real electrical-distance / loss estimation (replaces node-hop placeholder in P_loss)
- Congestion state per feeder segment (feeds P_congestion in pricing engine)
- Allocation rerouting when a path is congested or infeasible

Then refactor `backend/market_engine/auction.py` into `backend/pricing_engine/engine.py` to consume grid twin outputs.

---

## Agent Handoff Log

> Append a row when handing off. Record: what you built, current state, what the next agent should do.

| # | Agent | What Was Done | Next Step |
|---|---|---|---|
| 1 | Setup Agent | Read PDF plan. Created PROJECT_CONTEXT.md. | Scaffold structure + Phase 1 |
| 2 | Build Agent | Phase 1 complete: FastAPI backend, SQLite models, pricing engine (P_base+P_scarcity+placeholder loss/congestion), React dashboard, end-to-end test passing. | Phase 2: Grid Digital Twin |
| 3 | Architecture Agent | Realigned PROJECT_CONTEXT.md to centralised dynamic pricing + allocation architecture (replaced double-auction framing). Code unchanged; refactor of auction.py -> pricing_engine/engine.py is Phase 2 task. | Proceed with Phase 2 as described above |

---

## PHASE 2 STATUS: ✅ COMPLETE

### Built Files

**Grid Digital Twin (`backend/grid_twin/`)**
- `feeder.py` — 8-node radial feeder (nodes 1-8, 7 lines), BFS path finding, backward/forward loss estimation, per-line utilisation + congestion state, module-level singleton `feeder`

**Pricing & Allocation Engine (`backend/pricing_engine/`)**
- `engine.py` — Central Pricing + Allocation Engine (`run_allocation`). Reads grid twin state. Candidates scored by `electrical_distance + congestion_penalty`. Computes `P_final = P_base + P_scarcity + P_loss + P_congestion` with real feeder data. Injects flows into feeder twin after each allocation.
- `demand_response.py` — Flexible load scheduler (assigns loads to cheapest/highest-surplus blocks)

**API additions (`backend/api/market.py`)**
- `GET  /market/feeder` — Full feeder state snapshot (nodes, lines, flows, utilisation, congestion)
- `GET  /market/feeder/path?src=&dst=` — Path + electrical distance + residual capacity between two nodes
- `POST /market/feeder/reset` — Reset all flows (for demo scenarios)
- `POST /market/feeder/inject_congestion?line_id=&load_kw=` — Inject load on a specific line (demo trigger)

**Frontend (`frontend/src/`)**
- `FeederMap.tsx` — SVG feeder map: nodes coloured by type, lines coloured by utilisation (green → amber → red/dashed for congested), line utilisation % labels
- `App.tsx` — New "Feeder" tab with live feeder map, line detail table, demo controls (inject congestion / reset)

### Verified Working

- Feeder topology: 8 nodes, 7 lines, path finding correct
- Loss estimation: loss = (flow/V)^2 * R_pu per segment
- Congestion detection at 80% utilisation threshold
- Allocation rerouting: congested-path candidates deprioritised by score weighting
- Full allocation run: 7 kWh supply, 6 kWh demand, 6 kWh allocated across 4 trades, avg Rs 4.39/kWh, P_scarcity = -0.057 (surplus period)
- Frontend builds successfully (661 kB)
- 4 new feeder API endpoints verified

### How to Run

```
Terminal 1: cd backend  && uvicorn main:app --reload   -> http://localhost:8000/docs
Terminal 2: cd frontend && npm run dev                 -> http://localhost:5173
```

### Signature Demo Steps (Phase 2 ready)

1. Register 2 prosumers (Node 4 + Node 8) and 2-3 consumers (Nodes 5, 6, 7)
2. Submit supply + demand declarations for a time block
3. Click "Run Pricing & Allocation Engine" — see feeder map light up with flows
4. Go to Feeder tab → Inject Congestion on L1-2 (25 kW) — line turns red
5. Run engine again for same block — allocation reroutes away from L1-2
6. Price breakdown shows P_congestion added on remaining path

### What Is Next (Phase 3 → Phase 4)

Phase 3 — Allocation engine upgrade (already partly in Phase 2):
- [ ] Demonstrate benchmark: grid-only vs naive P2P vs grid-aware side-by-side
- [ ] Add demand response endpoint: accept flexible load declarations, return scheduled blocks

Phase 4 — Forecast engine:
- [ ] `backend/forecast_engine/forecast.py` — XGBoost solar/load forecaster
- [ ] Conservative TradableEnergy formula: `max(0, ForecastSurplus - k * ForecastError)`
- [ ] Wire forecast output into supply declarations automatically


---

## PHASE 3 + PHASE 4 STATUS: ✅ COMPLETE

### Built Files

**Benchmark Engine (`backend/benchmark/`)**
- `engine.py` — Runs same scenario in 3 modes in-memory (no DB side-effects):
  - Mode A: Grid-only — all consumption at RETAIL_PRICE (Rs 8/kWh), prosumer export at FEED_IN_TARIFF (Rs 2/kWh)
  - Mode B: Naive P2P — match by electrical distance only, flat BASE_PRICE, no line-capacity checks
  - Mode C: Grid-aware P2P — full centralised pricing + allocation engine with twin
  - Returns side-by-side metrics + delta comparisons C vs A

**Forecast Engine (`backend/forecast_engine/`)**
- `forecast.py` — XGBoost model trained on 30 days of synthetic household data (solar bell-curve + double-hump load)
  - Solar RMSE ≈ 0.053 kW, Load RMSE ≈ 0.096 kW
  - `TradableEnergy = max(0, ForecastSurplus - k * ForecastError)` (k=0.15)
  - Cloud cover slider reduces TradableEnergy to 0 when overcast
  - `forecast_day()` / `forecast_block()` / cloud scenario comparison

**API additions**
- `POST /benchmark/run` — custom scenario benchmark
- `GET  /benchmark/demo` — pre-built 3-prosumer/4-consumer demo scenario
- `GET  /forecast/day?date=&cloud_factor=` — full-day 96-interval forecast
- `GET  /forecast/block?time_block=` — single block forecast
- `GET  /forecast/scenario` — clear vs cloudy comparison

**Frontend (`frontend/src/App.tsx`) — 7 tabs**
- Benchmark tab: one-click demo benchmark, mode summary cards (A/B/C), horizontal bar chart comparison, delta summary
- Forecast tab: cloud-factor slider, solar+load area chart (clear vs overcast), TradableEnergy area chart with cloud-cover narrative

### Verified Working
- Benchmark demo: Mode A = Rs 8/kWh (grid), Mode B = Rs 4/kWh (naive P2P), Mode C = Rs 4.42/kWh (grid-aware with loss/congestion pricing)
- Prosumer revenue: A = Rs 2/kWh (feed-in), B = Rs 3.86/kWh, C = Rs 4.25/kWh
- Forecast: clear-sky 12:00 tradable = 0.539 kWh, overcast = 0 kWh (correct)
- Night-time tradable = 0 kWh (correct)
- Frontend build: ✅ 691 kB

### How to Run
```
Terminal 1: cd backend  && uvicorn main:app --reload  -> http://localhost:8000/docs
Terminal 2: cd frontend && npm run dev               -> http://localhost:5173
```

### What Is Next (Phase 5 — Trust Layer)
- `backend/meter_oracle/oracle.py` — signed meter simulator, hash generation, deviation calculation
- `blockchain/contracts/EnergyTrade.sol` — Solidity smart contract (Hardhat)
- Settlement lifecycle: commit -> meter verification -> release payment + emit event
- Add Settlement tab to dashboard showing on-chain records

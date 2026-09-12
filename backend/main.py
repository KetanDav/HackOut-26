from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HackOut26 — P2P Renewable Energy Trading Marketplace",
    description="""
Grid-aware peer-to-peer energy marketplace with centralised dynamic pricing and allocation.

**Architecture:** Users declare supply/demand → Grid Digital Twin + Forecast Engine →
Central Pricing & Allocation Engine → Dynamic P2P Price + Prosumer→Consumer Allocation →
Meter Oracle → Smart Contract Settlement → Blockchain Audit Record.

**Pricing:** P_final = P_base + P_scarcity + P_loss + P_congestion
    """,
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.users      import router as users_router
from api.orders     import router as orders_router
from api.market     import router as market_router
from api.benchmark  import router as benchmark_router
from api.forecast   import router as forecast_router

app.include_router(users_router)
app.include_router(orders_router)
app.include_router(market_router)
app.include_router(benchmark_router)
app.include_router(forecast_router)

@app.get("/")
def root():
    return {
        "project": "HackOut26 — Grid-Aware P2P Renewable Energy Trading Marketplace",
        "version": "2.0.0 (Phase 3 + 4)",
        "docs": "/docs",
        "key_endpoints": {
            "users":            "/users",
            "declarations":     "/orders",
            "allocation_engine":"/market/clear/{time_block}",
            "trades":           "/market/trades",
            "feeder_state":     "/market/feeder",
            "inject_congestion":"/market/feeder/inject_congestion",
            "benchmark":        "/benchmark/demo",
            "forecast_day":     "/forecast/day",
            "forecast_scenario":"/forecast/scenario",
        },
    }

@app.get("/health")
def health():
    return {"status": "ok"}
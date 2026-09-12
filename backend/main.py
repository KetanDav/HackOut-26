from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models

# Create all DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HackOut26 — P2P Renewable Energy Trading Marketplace",
    description="Grid-aware peer-to-peer energy trading with dynamic pricing and blockchain settlement.",
    version="1.0.0"
)

# Allow React frontend on localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from api.users import router as users_router
from api.orders import router as orders_router
from api.market import router as market_router

app.include_router(users_router)
app.include_router(orders_router)
app.include_router(market_router)

@app.get("/")
def root():
    return {
        "project": "HackOut26 — P2P Renewable Energy Trading Marketplace",
        "phase": "Phase 1 — Core Market",
        "docs": "/docs",
        "endpoints": {
            "users": "/users",
            "orders": "/orders",
            "market_clear": "/market/clear/{time_block}",
            "trades": "/market/trades",
            "summary": "/market/summary",
        }
    }

@app.get("/health")
def health():
    return {"status": "ok"}

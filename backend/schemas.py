from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# ── Users ─────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: str
    role: str = "consumer"   # prosumer | consumer | both
    node_id: int = 1
    solar_capacity_kw: float = 0.0

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    node_id: int
    solar_capacity_kw: float
    created_at: datetime
    class Config:
        from_attributes = True

# ── Orders ────────────────────────────────────────
class OrderCreate(BaseModel):
    user_id: int
    order_type: str        # sell | buy
    energy_kwh: float
    price_per_kwh: float   # min ask for sell; max bid for buy
    time_block: str        # "2026-09-12 10:00"  (15-min block start)
    node_id: int

class OrderOut(BaseModel):
    id: int
    user_id: int
    order_type: str
    energy_kwh: float
    remaining_kwh: float
    price_per_kwh: float
    time_block: str
    node_id: int
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

# ── Trades ────────────────────────────────────────
class TradeOut(BaseModel):
    id: int
    sell_order_id: int
    buy_order_id: int
    seller_id: int
    buyer_id: int
    energy_kwh: float
    clearing_price: float
    price_scarcity: float
    price_loss: float
    price_congestion: float
    final_price: float
    seller_node: Optional[int]
    buyer_node: Optional[int]
    time_block: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

# ── Market Run ────────────────────────────────────
class MarketRunOut(BaseModel):
    id: int
    time_block: str
    total_sell_kwh: float
    total_buy_kwh: float
    total_cleared_kwh: float
    clearing_price: float
    trades_count: int
    ran_at: datetime
    trades: List[TradeOut] = []
    class Config:
        from_attributes = True

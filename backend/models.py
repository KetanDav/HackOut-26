from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class UserRole(str, enum.Enum):
    PROSUMER = "prosumer"   # has solar, can sell surplus
    CONSUMER = "consumer"   # only buys
    BOTH = "both"           # prosumer who also buys

class OrderType(str, enum.Enum):
    SELL = "sell"
    BUY = "buy"

class OrderStatus(str, enum.Enum):
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"

class TradeStatus(str, enum.Enum):
    COMMITTED = "committed"
    DELIVERED = "delivered"
    SETTLED = "settled"
    DISPUTED = "disputed"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default=UserRole.CONSUMER)
    node_id = Column(Integer, nullable=False, default=1)   # feeder node where user is connected
    solar_capacity_kw = Column(Float, default=0.0)         # installed solar capacity (kW)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_type = Column(String, nullable=False)            # sell / buy
    energy_kwh = Column(Float, nullable=False)             # quantity in kWh
    remaining_kwh = Column(Float, nullable=False)          # unfilled quantity
    price_per_kwh = Column(Float, nullable=False)          # min ask (sell) or max bid (buy)
    time_block = Column(String, nullable=False)            # "YYYY-MM-DD HH:MM" 15-min slot start
    node_id = Column(Integer, nullable=False)              # feeder node
    status = Column(String, default=OrderStatus.OPEN)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    sell_order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    buy_order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    energy_kwh = Column(Float, nullable=False)              # cleared quantity
    clearing_price = Column(Float, nullable=False)          # P_market
    price_scarcity = Column(Float, default=0.0)             # P_scarcity component
    price_loss = Column(Float, default=0.0)                 # P_loss component
    price_congestion = Column(Float, default=0.0)           # P_congestion component
    final_price = Column(Float, nullable=False)             # P_final = sum of all components
    seller_node = Column(Integer)
    buyer_node = Column(Integer)
    time_block = Column(String, nullable=False)
    status = Column(String, default=TradeStatus.COMMITTED)
    created_at = Column(DateTime, default=datetime.utcnow)

class MarketRun(Base):
    __tablename__ = "market_runs"

    id = Column(Integer, primary_key=True, index=True)
    time_block = Column(String, nullable=False, index=True)
    total_sell_kwh = Column(Float, default=0.0)
    total_buy_kwh = Column(Float, default=0.0)
    total_cleared_kwh = Column(Float, default=0.0)
    clearing_price = Column(Float, default=0.0)
    trades_count = Column(Integer, default=0)
    ran_at = Column(DateTime, default=datetime.utcnow)

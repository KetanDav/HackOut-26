from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from market_engine.auction import clear_market

router = APIRouter(prefix="/market", tags=["Market"])

@router.post("/clear/{time_block}")
def run_market_clearing(time_block: str, db: Session = Depends(get_db)):
    """
    Trigger market clearing for a specific 15-min time block.
    time_block format: "2026-09-12 10:00"
    """
    result = clear_market(time_block, db)
    return result

@router.get("/trades", response_model=list[schemas.TradeOut])
def list_trades(time_block: str = None, db: Session = Depends(get_db)):
    q = db.query(models.Trade)
    if time_block:
        q = q.filter(models.Trade.time_block == time_block)
    return q.order_by(models.Trade.created_at.desc()).all()

@router.get("/trades/{trade_id}", response_model=schemas.TradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade

@router.get("/runs")
def list_market_runs(db: Session = Depends(get_db)):
    runs = db.query(models.MarketRun).order_by(models.MarketRun.ran_at.desc()).all()
    return runs

@router.get("/summary")
def market_summary(db: Session = Depends(get_db)):
    """Quick stats for the dashboard."""
    total_users = db.query(models.User).count()
    open_sells = db.query(models.Order).filter(
        models.Order.order_type == "sell",
        models.Order.status == "open"
    ).count()
    open_buys = db.query(models.Order).filter(
        models.Order.order_type == "buy",
        models.Order.status == "open"
    ).count()
    total_trades = db.query(models.Trade).count()
    total_cleared = db.query(models.Trade).all()
    cleared_kwh = sum(t.energy_kwh for t in total_trades if hasattr(t, "energy_kwh")) if total_trades else 0

    trades = db.query(models.Trade).all()
    cleared_kwh = sum(t.energy_kwh for t in trades)
    avg_price = round(
        sum(t.final_price * t.energy_kwh for t in trades) / cleared_kwh, 4
    ) if cleared_kwh > 0 else 0.0

    return {
        "total_users": total_users,
        "open_sell_orders": open_sells,
        "open_buy_orders": open_buys,
        "total_trades": len(trades),
        "total_cleared_kwh": round(cleared_kwh, 4),
        "avg_final_price": avg_price,
    }

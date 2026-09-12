from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from pricing_engine.engine import run_allocation
from grid_twin.feeder import feeder as FEEDER, NODES

router = APIRouter(prefix="/market", tags=["Market"])


@router.post("/clear/{time_block}")
def run_market_clearing(time_block: str, db: Session = Depends(get_db)):
    """
    Trigger the Pricing + Allocation Engine for a 15-min time block.
    time_block format: "2026-09-12 10:00"
    """
    result = run_allocation(time_block, db)
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
    return db.query(models.MarketRun).order_by(models.MarketRun.ran_at.desc()).all()


@router.get("/summary")
def market_summary(db: Session = Depends(get_db)):
    """Quick stats for the dashboard header badges."""
    total_users = db.query(models.User).count()
    open_sells = db.query(models.Order).filter(
        models.Order.order_type == "sell", models.Order.status == "open"
    ).count()
    open_buys = db.query(models.Order).filter(
        models.Order.order_type == "buy", models.Order.status == "open"
    ).count()
    trades = db.query(models.Trade).all()
    cleared_kwh = sum(t.energy_kwh for t in trades)
    avg_price = (
        round(sum(t.final_price * t.energy_kwh for t in trades) / cleared_kwh, 4)
        if cleared_kwh > 0 else 0.0
    )
    return {
        "total_users": total_users,
        "open_sell_orders": open_sells,
        "open_buy_orders": open_buys,
        "total_trades": len(trades),
        "total_cleared_kwh": round(cleared_kwh, 4),
        "avg_final_price": avg_price,
    }


@router.get("/feeder")
def get_feeder_state():
    """
    Current Grid Digital Twin state — node list, per-line flows,
    utilisation, congestion flags, and total losses.
    Used by the dashboard feeder map.
    """
    return FEEDER.state_snapshot()


@router.get("/feeder/path")
def get_path(src: int, dst: int):
    """Node path and electrical distance between two feeder nodes."""
    path = FEEDER.path_between(src, dst)
    elec_dist = FEEDER.electrical_distance(src, dst)
    residual = FEEDER.residual_capacity_kw(src, dst)
    return {
        "src": src,
        "dst": dst,
        "path": path,
        "electrical_distance_pu": round(elec_dist, 4),
        "residual_capacity_kw": round(residual, 4),
    }


@router.post("/feeder/reset")
def reset_feeder():
    """Reset all feeder flows to zero (for demo scenarios)."""
    FEEDER.reset_flows()
    return {"message": "Feeder flows reset.", "state": FEEDER.state_snapshot()}


@router.post("/feeder/inject_congestion")
def inject_congestion(line_id: str, load_kw: float = 18.0):
    """
    Demo helper: manually inject load on a feeder line to trigger congestion.
    Useful for the signature demo moment.
    """
    ln = FEEDER.lines.get(line_id)
    if not ln:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found. Available: {list(FEEDER.lines.keys())}")
    ln.flow_kw += load_kw
    return {
        "message": f"Injected {load_kw} kW on {line_id}.",
        "utilisation": round(ln.utilisation, 4),
        "is_congested": ln.is_congested,
        "state": FEEDER.state_snapshot(),
    }
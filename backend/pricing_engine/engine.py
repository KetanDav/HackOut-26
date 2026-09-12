"""
pricing_engine/engine.py
------------------------
Central Pricing + Allocation Engine (replaces market_engine/auction.py).

Runs once per 15-minute time block:
  1. Collects prosumer surplus declarations and consumer demand declarations.
  2. Queries the Grid Digital Twin for network state.
  3. Computes dynamic price components:
       P_final = P_base + P_scarcity + P_loss + P_congestion
  4. Allocates prosumer surplus to consumers, preferring electrically
     favourable paths and rejecting/rerouting congested ones.
  5. Returns allocation records (Trades) and a feeder state snapshot.

No bidding or order-book. Users declare availability/requirements;
the engine prices and allocates automatically.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
import models
from grid_twin.feeder import feeder as FEEDER
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable parameters
# ---------------------------------------------------------------------------

BASE_PRICE_PER_KWH = 4.0            # Rs/kWh  — local market reference price
SCARCITY_CAP = 0.8                  # max scarcity premium (Rs/kWh)
LOSS_COST_PER_KW = 3.0              # Rs/kWh per pu resistance unit on path
CONGESTION_LAMBDA = 0.5             # congestion premium coefficient
CONGESTION_TAU = 0.80               # feeder utilisation threshold (80%)
MIN_ALLOCATION_KWH = 0.01           # ignore allocations below this


# ---------------------------------------------------------------------------
# Price component functions
# ---------------------------------------------------------------------------

def _p_scarcity(total_supply_kwh: float, total_demand_kwh: float) -> float:
    """
    P_scarcity: premium when local demand exceeds local supply.
    Negative (discount) when supply exceeds demand.
    """
    if total_supply_kwh <= 0:
        return SCARCITY_CAP
    ratio = total_demand_kwh / total_supply_kwh
    raw = (ratio - 1.0) * 0.4          # 0.4 Rs/kWh per unit demand/supply ratio
    return round(max(-0.5, min(raw, SCARCITY_CAP)), 4)


def _p_loss(src_node: int, dst_node: int, flow_kwh: float) -> float:
    """
    P_loss: delivery loss cost for the prosumer→consumer path.
    Based on estimated kW losses and a cost-per-kW multiplier.
    """
    loss_kw = FEEDER.estimate_loss_kw(flow_kwh, src_node, dst_node)
    cost = loss_kw * LOSS_COST_PER_KW
    return round(min(cost, 1.0), 4)     # cap at 1.0 Rs/kWh


def _p_congestion(src_node: int, dst_node: int) -> Tuple[float, bool]:
    """
    P_congestion: premium when any line on the path is congested.
    Returns (congestion_cost, path_is_blocked).
    Path is blocked only if utilisation would exceed 100%.
    """
    path = FEEDER.path_between(src_node, dst_node)
    lines = FEEDER.lines_on_path(path)
    max_util = max((ln.utilisation for ln in lines), default=0.0)

    if max_util >= 1.0:
        return (0.0, True)      # completely infeasible path

    if max_util < CONGESTION_TAU:
        return (0.0, False)

    cost = CONGESTION_LAMBDA * (max_util - CONGESTION_TAU)
    return (round(min(cost, 1.0), 4), False)


# ---------------------------------------------------------------------------
# Main allocation function
# ---------------------------------------------------------------------------

def run_allocation(time_block: str, db: Session) -> Dict[str, Any]:
    """
    Core engine entry point. Allocates local renewable surplus to consumers
    for a given 15-minute time block and records Trade objects in the DB.
    """
    # 1. Load open supply (sell) and demand (buy) orders for this block
    supplies = (
        db.query(models.Order)
        .filter(
            models.Order.time_block == time_block,
            models.Order.order_type == "sell",
            models.Order.status.in_(["open", "partially_filled"]),
        )
        .order_by(models.Order.created_at.asc())
        .all()
    )
    demands = (
        db.query(models.Order)
        .filter(
            models.Order.time_block == time_block,
            models.Order.order_type == "buy",
            models.Order.status.in_(["open", "partially_filled"]),
        )
        .order_by(models.Order.created_at.asc())
        .all()
    )

    total_supply = sum(o.remaining_kwh for o in supplies)
    total_demand = sum(o.remaining_kwh for o in demands)

    if not supplies or not demands:
        snap = FEEDER.state_snapshot()
        return {
            "time_block": time_block,
            "message": "Insufficient supply or demand declarations for this block.",
            "total_supply_kwh": total_supply,
            "total_demand_kwh": total_demand,
            "total_allocated_kwh": 0.0,
            "trades": [],
            "feeder_state": snap,
        }

    # 2. Reset feeder flows for a clean allocation run
    FEEDER.reset_flows()

    # 3. Market-level scarcity component (same for all trades this block)
    p_scarcity = _p_scarcity(total_supply, total_demand)

    # 4. Build candidate pairs: every (supply, demand) combo for this block
    #    Scored by total effective delivered cost; lower is preferred.
    candidates: List[Dict] = []
    for sup in supplies:
        for dem in demands:
            # Skip if different time blocks (shouldn't happen, but guard)
            if sup.time_block != dem.time_block:
                continue
            residual_cap = FEEDER.residual_capacity_kw(sup.node_id, dem.node_id)
            if residual_cap <= 0:
                continue  # no capacity on path
            candidates.append({
                "supply": sup,
                "demand": dem,
                "elec_dist": FEEDER.electrical_distance(sup.node_id, dem.node_id),
                "residual_cap_kw": residual_cap,
            })

    # Score candidates by total effective network cost:
    #   electrical_distance (loss proxy) + congestion cost on path.
    # This makes the engine visibly reroute away from congested paths
    # even before a line hits 100% capacity — the key demo behaviour.
    def _candidate_score(c: Dict) -> float:
        cong_cost, _ = _p_congestion(c["supply"].node_id, c["demand"].node_id)
        return c["elec_dist"] + cong_cost * 10   # weight congestion heavily

    candidates.sort(key=_candidate_score)

    # 5. Greedy allocation loop
    trades_created: List[models.Trade] = []
    total_allocated = 0.0

    for cand in candidates:
        sup = cand["supply"]
        dem = cand["demand"]

        if sup.remaining_kwh <= MIN_ALLOCATION_KWH:
            continue
        if dem.remaining_kwh <= MIN_ALLOCATION_KWH:
            continue

        # Re-check path after previous injections
        p_cong, blocked = _p_congestion(sup.node_id, dem.node_id)
        if blocked:
            logger.info(
                f"[Engine] Path {sup.node_id}→{dem.node_id} is fully congested — skipping."
            )
            continue

        # Quantity: limited by supply remaining, demand remaining, and path capacity
        qty = min(
            sup.remaining_kwh,
            dem.remaining_kwh,
            FEEDER.residual_capacity_kw(sup.node_id, dem.node_id),
        )
        if qty <= MIN_ALLOCATION_KWH:
            continue

        # Price components for this specific allocation
        p_loss = _p_loss(sup.node_id, dem.node_id, qty)
        p_final = round(BASE_PRICE_PER_KWH + p_scarcity + p_loss + p_cong, 4)

        # Inject flow into feeder twin
        FEEDER.inject_allocation(sup.node_id, dem.node_id, qty)

        # Create Trade record
        trade = models.Trade(
            sell_order_id=sup.id,
            buy_order_id=dem.id,
            seller_id=sup.user_id,
            buyer_id=dem.user_id,
            energy_kwh=round(qty, 4),
            clearing_price=BASE_PRICE_PER_KWH,
            price_scarcity=p_scarcity,
            price_loss=p_loss,
            price_congestion=p_cong,
            final_price=p_final,
            seller_node=sup.node_id,
            buyer_node=dem.node_id,
            time_block=time_block,
            status="committed",
        )
        db.add(trade)

        # Update declaration quantities
        sup.remaining_kwh = round(sup.remaining_kwh - qty, 4)
        dem.remaining_kwh = round(dem.remaining_kwh - qty, 4)
        sup.status = "filled" if sup.remaining_kwh <= MIN_ALLOCATION_KWH else "partially_filled"
        dem.status = "filled" if dem.remaining_kwh <= MIN_ALLOCATION_KWH else "partially_filled"

        total_allocated += qty
        trades_created.append(trade)

    db.flush()

    # 6. Record market run summary
    avg_price = round(
        sum(t.final_price * t.energy_kwh for t in trades_created) / total_allocated, 4
    ) if total_allocated > 0 else 0.0

    run = models.MarketRun(
        time_block=time_block,
        total_sell_kwh=total_supply,
        total_buy_kwh=total_demand,
        total_cleared_kwh=round(total_allocated, 4),
        clearing_price=avg_price,
        trades_count=len(trades_created),
    )
    db.add(run)
    db.commit()

    for t in trades_created:
        db.refresh(t)

    feeder_snap = FEEDER.state_snapshot()

    logger.info(
        f"[Engine] {time_block}: allocated {total_allocated:.2f} kWh "
        f"across {len(trades_created)} trades @ avg Rs {avg_price:.4f}/kWh | "
        f"peak feeder util: {feeder_snap['peak_utilisation']:.1%} | "
        f"congested lines: {feeder_snap['congested_lines']}"
    )

    return {
        "time_block": time_block,
        "total_supply_kwh": total_supply,
        "total_demand_kwh": total_demand,
        "total_allocated_kwh": round(total_allocated, 4),
        "surplus_exported_kwh": round(total_supply - total_allocated, 4),
        "avg_final_price": avg_price,
        "p_base": BASE_PRICE_PER_KWH,
        "p_scarcity": p_scarcity,
        "trades_count": len(trades_created),
        "feeder_state": feeder_snap,
        "trades": [
            {
                "id": t.id,
                "seller_id": t.seller_id,
                "buyer_id": t.buyer_id,
                "energy_kwh": t.energy_kwh,
                "seller_node": t.seller_node,
                "buyer_node": t.buyer_node,
                "p_base": t.clearing_price,
                "p_scarcity": t.price_scarcity,
                "p_loss": t.price_loss,
                "p_congestion": t.price_congestion,
                "final_price": t.final_price,
            }
            for t in trades_created
        ],
    }
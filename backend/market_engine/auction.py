"""
Double Auction Market Clearing Engine — Phase 1 (Basic)
Phase 2 will add grid constraints from grid_twin module.

Clears one 15-minute time_block at a time:
  1. Collect open SELL and BUY orders for that block.
  2. Sort sells ascending (cheapest first), buys descending (highest bid first).
  3. Find clearing price where cumulative supply meets cumulative demand.
  4. Match orders greedily, create Trade records.
  5. Apply basic dynamic pricing components (scarcity, placeholder loss/congestion).
"""

from typing import List, Tuple
from sqlalchemy.orm import Session
import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _scarcity_component(total_demand: float, total_supply: float) -> float:
    """
    P_scarcity: price premium when demand > supply.
    Returns a positive adjustment when supply is scarce.
    """
    if total_supply <= 0:
        return 0.5  # max scarcity if no supply
    ratio = total_demand / total_supply  # > 1 means excess demand
    if ratio <= 1.0:
        return 0.0   # surplus supply, no scarcity premium
    return round(min((ratio - 1.0) * 0.5, 0.5), 4)  # capped at 0.5 Rs/kWh


def _loss_component(seller_node: int, buyer_node: int) -> float:
    """
    P_loss: delivery loss cost based on node distance.
    Phase 2 will replace with real feeder path calculation.
    For now: 0.01 Rs/kWh per node hop (placeholder).
    """
    hops = abs(seller_node - buyer_node)
    return round(hops * 0.01, 4)


def _congestion_component(seller_node: int, buyer_node: int, line_load: float = 0.0) -> float:
    """
    P_congestion: cost when feeder segment utilization exceeds threshold tau.
    Phase 2 will use real feeder flow data.
    For now: returns 0 (no congestion in Phase 1).
    """
    tau = 0.8   # congestion threshold (80% utilization)
    lambda_c = 0.2
    if line_load <= tau:
        return 0.0
    return round(lambda_c * (line_load - tau), 4)


def clear_market(time_block: str, db: Session) -> dict:
    """
    Run double auction for a given time block.
    Returns a summary dict with trades created.
    """
    # 1. Fetch open orders for this time block
    sells = db.query(models.Order).filter(
        models.Order.time_block == time_block,
        models.Order.order_type == models.OrderType.SELL,
        models.Order.status.in_([models.OrderStatus.OPEN, models.OrderStatus.PARTIALLY_FILLED])
    ).order_by(models.Order.price_per_kwh.asc()).all()   # cheapest seller first

    buys = db.query(models.Order).filter(
        models.Order.time_block == time_block,
        models.Order.order_type == models.OrderType.BUY,
        models.Order.status.in_([models.OrderStatus.OPEN, models.OrderStatus.PARTIALLY_FILLED])
    ).order_by(models.Order.price_per_kwh.desc()).all()  # highest bidder first

    total_supply = sum(o.remaining_kwh for o in sells)
    total_demand = sum(o.remaining_kwh for o in buys)

    if not sells or not buys:
        return {
            "time_block": time_block,
            "message": "No matching orders — need both sell and buy orders.",
            "total_sell_kwh": total_supply,
            "total_buy_kwh": total_demand,
            "trades": []
        }

    # 2. Scarcity component (market-level, same for all trades in this run)
    p_scarcity = _scarcity_component(total_demand, total_supply)

    # 3. Greedy matching: iterate buys (high to low), match with sells (low to high)
    trades_created = []
    total_cleared = 0.0

    sell_idx = 0
    for buy_order in buys:
        if sell_idx >= len(sells):
            break
        if buy_order.remaining_kwh <= 0:
            continue

        while sell_idx < len(sells) and buy_order.remaining_kwh > 0:
            sell_order = sells[sell_idx]

            if sell_order.remaining_kwh <= 0:
                sell_idx += 1
                continue

            # Economic feasibility check: buyer must bid >= seller ask (before network costs)
            if buy_order.price_per_kwh < sell_order.price_per_kwh:
                break  # no more profitable matches for this buyer

            # Clearing price = midpoint (standard double auction)
            clearing_price = round((sell_order.price_per_kwh + buy_order.price_per_kwh) / 2, 4)

            # Network cost components
            p_loss = _loss_component(sell_order.node_id, buy_order.node_id)
            p_congestion = _congestion_component(sell_order.node_id, buy_order.node_id)

            final_price = round(clearing_price + p_scarcity + p_loss + p_congestion, 4)

            # Buyer surplus check (buyer must still benefit after network costs)
            buyer_surplus = buy_order.price_per_kwh - final_price
            if buyer_surplus < 0:
                # This specific seller-buyer pair is too expensive due to network costs
                sell_idx += 1
                continue

            # Cleared quantity = min of remaining on both sides
            cleared_qty = round(min(sell_order.remaining_kwh, buy_order.remaining_kwh), 4)

            # Create trade record
            trade = models.Trade(
                sell_order_id=sell_order.id,
                buy_order_id=buy_order.id,
                seller_id=sell_order.user_id,
                buyer_id=buy_order.user_id,
                energy_kwh=cleared_qty,
                clearing_price=clearing_price,
                price_scarcity=p_scarcity,
                price_loss=p_loss,
                price_congestion=p_congestion,
                final_price=final_price,
                seller_node=sell_order.node_id,
                buyer_node=buy_order.node_id,
                time_block=time_block,
                status=models.TradeStatus.COMMITTED
            )
            db.add(trade)

            # Update order quantities
            sell_order.remaining_kwh = round(sell_order.remaining_kwh - cleared_qty, 4)
            buy_order.remaining_kwh = round(buy_order.remaining_kwh - cleared_qty, 4)

            # Update order statuses
            sell_order.status = models.OrderStatus.FILLED if sell_order.remaining_kwh == 0 else models.OrderStatus.PARTIALLY_FILLED
            buy_order.status = models.OrderStatus.FILLED if buy_order.remaining_kwh == 0 else models.OrderStatus.PARTIALLY_FILLED

            if sell_order.remaining_kwh == 0:
                sell_idx += 1

            total_cleared += cleared_qty
            trades_created.append(trade)

    db.flush()

    # 4. Market run record
    avg_clearing_price = round(
        sum(t.final_price * t.energy_kwh for t in trades_created) / total_cleared, 4
    ) if total_cleared > 0 else 0.0

    run = models.MarketRun(
        time_block=time_block,
        total_sell_kwh=total_supply,
        total_buy_kwh=total_demand,
        total_cleared_kwh=total_cleared,
        clearing_price=avg_clearing_price,
        trades_count=len(trades_created)
    )
    db.add(run)
    db.commit()

    for t in trades_created:
        db.refresh(t)

    logger.info(f"[Market] {time_block}: cleared {total_cleared:.2f} kWh across {len(trades_created)} trades @ avg {avg_clearing_price:.4f}")

    return {
        "time_block": time_block,
        "total_sell_kwh": total_supply,
        "total_buy_kwh": total_demand,
        "total_cleared_kwh": total_cleared,
        "avg_final_price": avg_clearing_price,
        "p_scarcity": p_scarcity,
        "trades_count": len(trades_created),
        "trades": [
            {
                "id": t.id,
                "seller_id": t.seller_id,
                "buyer_id": t.buyer_id,
                "energy_kwh": t.energy_kwh,
                "clearing_price": t.clearing_price,
                "price_scarcity": t.price_scarcity,
                "price_loss": t.price_loss,
                "price_congestion": t.price_congestion,
                "final_price": t.final_price,
                "seller_node": t.seller_node,
                "buyer_node": t.buyer_node,
            }
            for t in trades_created
        ]
    }

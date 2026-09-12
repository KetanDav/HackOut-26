"""
pricing_engine/demand_response.py
----------------------------------
Flexible demand scheduling.

Consumers with flexible loads (e.g. EV charging) declare:
  - total energy required (kWh)
  - deadline (e.g. "07:00")
  - flexibility window (list of acceptable time blocks)

The scheduler assigns demand to time blocks where local renewable surplus
is highest and dynamic price is lowest, without the user needing to
monitor prices manually.

In Phase 4 this will be connected to the forecast engine output.
For Phase 2/3 it uses a simple surplus-then-price sort.
"""

from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class FlexibleLoad:
    consumer_id: int
    node_id: int
    total_kwh: float                # total energy required
    deadline_block: str             # latest acceptable time block ("YYYY-MM-DD HH:MM")
    allowed_blocks: List[str]       # ordered list of eligible time blocks


def schedule_flexible_demand(
    loads: List[FlexibleLoad],
    block_supply_kwh: Dict[str, float],     # {time_block: estimated_surplus_kwh}
    block_price: Dict[str, float],          # {time_block: current_avg_price}
) -> List[Dict[str, Any]]:
    """
    Assign each flexible load to time blocks.
    Prefers blocks with high surplus (low price implied) first.
    Returns a list of scheduled demand declarations.
    """
    # Sort blocks by price ascending (cheapest / most surplus first)
    ranked_blocks = sorted(
        block_price.keys(),
        key=lambda b: (block_price.get(b, 999), -block_supply_kwh.get(b, 0))
    )

    scheduled = []
    for load in loads:
        remaining = load.total_kwh
        eligible = [b for b in ranked_blocks if b in load.allowed_blocks and b <= load.deadline_block]

        for block in eligible:
            if remaining <= 0:
                break
            available = block_supply_kwh.get(block, 0.0)
            allocated = min(remaining, available)
            if allocated <= 0:
                continue
            scheduled.append({
                "consumer_id": load.consumer_id,
                "node_id": load.node_id,
                "time_block": block,
                "scheduled_kwh": round(allocated, 4),
                "reason": "surplus_window",
            })
            remaining -= allocated
            block_supply_kwh[block] = max(0.0, available - allocated)

        if remaining > 0:
            scheduled.append({
                "consumer_id": load.consumer_id,
                "node_id": load.node_id,
                "time_block": load.deadline_block,
                "scheduled_kwh": round(remaining, 4),
                "reason": "deadline_fallback",
            })

    return scheduled
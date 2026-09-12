"""
benchmark/engine.py
--------------------
Runs the same scenario in three modes and returns comparative metrics.

Mode A  — Grid-only:
    All consumption from the grid at RETAIL_PRICE. No P2P.
    Prosumer surplus exported at FEED_IN_TARIFF.

Mode B  — Naive P2P (proximity-only, no network constraints):
    Prosumers matched to consumers by shortest electrical path,
    no line-capacity checks, no congestion cost.
    Price = BASE_PRICE (flat, no network component).

Mode C  — Grid-aware P2P (our engine):
    Full centralised pricing + allocation engine with grid digital twin.
    P_final = P_base + P_scarcity + P_loss + P_congestion.
    Congested paths are deprioritised / rejected.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any
import copy, math

from grid_twin.feeder import Feeder, NODES, _LINE_DEFS
from pricing_engine.engine import (
    BASE_PRICE_PER_KWH, CONGESTION_TAU, CONGESTION_LAMBDA,
    _p_scarcity, _p_loss, _p_congestion,
)

# ── Tariff constants ──────────────────────────────────────────────
RETAIL_PRICE    = 8.0    # Rs/kWh — grid retail rate consumers normally pay
FEED_IN_TARIFF  = 2.0    # Rs/kWh — low rate prosumers get for grid export
BASE_PRICE      = BASE_PRICE_PER_KWH   # P2P base price


# ── Scenario data structures ──────────────────────────────────────
@dataclass
class ProsumerDecl:
    pid: int
    node_id: int
    surplus_kwh: float      # available surplus

@dataclass
class ConsumerDecl:
    cid: int
    node_id: int
    demand_kwh: float       # energy required


# ── Metric container ──────────────────────────────────────────────
@dataclass
class ScenarioResult:
    mode: str
    label: str
    consumer_total_cost: float = 0.0         # Rs paid by all consumers
    consumer_avg_price: float  = 0.0         # Rs/kWh average
    prosumer_revenue: float    = 0.0         # Rs earned by prosumers
    prosumer_avg_price: float  = 0.0         # Rs/kWh earned
    p2p_share_pct: float       = 0.0         # % of demand met by P2P
    network_loss_kw: float     = 0.0         # total feeder losses kW
    peak_utilisation: float    = 0.0         # peak line utilisation (fraction)
    congestion_violations: int = 0           # lines that exceeded 100% capacity
    surplus_exported_kwh: float = 0.0        # surplus not traded locally
    trades: List[Dict]         = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "label": self.label,
            "consumer_total_cost_rs": round(self.consumer_total_cost, 4),
            "consumer_avg_price_rs_kwh": round(self.consumer_avg_price, 4),
            "prosumer_revenue_rs": round(self.prosumer_revenue, 4),
            "prosumer_avg_price_rs_kwh": round(self.prosumer_avg_price, 4),
            "p2p_share_pct": round(self.p2p_share_pct, 2),
            "network_loss_kw": round(self.network_loss_kw, 4),
            "peak_utilisation_pct": round(self.peak_utilisation * 100, 2),
            "congestion_violations": self.congestion_violations,
            "surplus_exported_kwh": round(self.surplus_exported_kwh, 4),
            "trades": self.trades,
        }


# ── Mode A: Grid-only ─────────────────────────────────────────────
def run_grid_only(prosumers: List[ProsumerDecl], consumers: List[ConsumerDecl]) -> ScenarioResult:
    r = ScenarioResult(mode="A", label="Grid-only (no P2P)")
    total_demand = sum(c.demand_kwh for c in consumers)
    total_surplus = sum(p.surplus_kwh for p in prosumers)

    r.consumer_total_cost = total_demand * RETAIL_PRICE
    r.consumer_avg_price  = RETAIL_PRICE
    r.prosumer_revenue    = total_surplus * FEED_IN_TARIFF
    r.prosumer_avg_price  = FEED_IN_TARIFF
    r.p2p_share_pct       = 0.0
    r.network_loss_kw     = 0.0   # centralised grid losses not modelled here
    r.peak_utilisation    = 0.0
    r.congestion_violations = 0
    r.surplus_exported_kwh = total_surplus
    return r


# ── Mode B: Naive P2P (proximity only, no network limits) ─────────
def run_naive_p2p(prosumers: List[ProsumerDecl], consumers: List[ConsumerDecl]) -> ScenarioResult:
    r = ScenarioResult(mode="B", label="Naive P2P (proximity, no network constraints)")
    f = Feeder()   # fresh twin for loss tracking only

    supply = {p.pid: p.surplus_kwh for p in prosumers}
    demand = {c.cid: c.demand_kwh  for c in consumers}

    total_demand  = sum(demand.values())
    total_supply  = sum(supply.values())

    # Build pairs sorted by electrical distance (no capacity limit applied)
    pairs = sorted(
        [(p, c) for p in prosumers for c in consumers],
        key=lambda x: f.electrical_distance(x[0].node_id, x[1].node_id)
    )

    total_allocated = 0.0
    total_cost      = 0.0
    total_revenue   = 0.0
    violations      = 0

    for pro, con in pairs:
        avail  = supply[pro.pid]
        needed = demand[con.cid]
        if avail <= 0 or needed <= 0:
            continue
        qty = min(avail, needed)
        # Flat BASE_PRICE — no network cost applied in naive mode
        price = BASE_PRICE
        # Still inject into twin to track losses and detect violations
        f.inject_allocation(pro.node_id, con.node_id, qty)
        supply[pro.pid] -= qty
        demand[con.cid] -= qty
        total_allocated += qty
        total_cost      += qty * price
        total_revenue   += qty * price
        r.trades.append({
            "seller_node": pro.node_id, "buyer_node": con.node_id,
            "kwh": round(qty, 4), "price": price,
        })

    # Count violations (lines over 100%)
    snap = f.state_snapshot()
    for ln in snap["lines"]:
        if ln["utilisation"] > 1.0:
            violations += 1

    consumed_from_grid = max(0, total_demand - total_allocated)
    total_cost += consumed_from_grid * RETAIL_PRICE

    exported = sum(supply.values())
    total_revenue += exported * FEED_IN_TARIFF

    r.consumer_total_cost  = total_cost
    r.consumer_avg_price   = total_cost / total_demand if total_demand > 0 else 0
    r.prosumer_revenue     = total_revenue
    r.prosumer_avg_price   = total_revenue / total_supply if total_supply > 0 else 0
    r.p2p_share_pct        = (total_allocated / total_demand * 100) if total_demand > 0 else 0
    r.network_loss_kw      = snap["total_loss_kw"]
    r.peak_utilisation     = snap["peak_utilisation"]
    r.congestion_violations = violations
    r.surplus_exported_kwh = exported
    return r


# ── Mode C: Grid-aware P2P ────────────────────────────────────────
def run_grid_aware(prosumers: List[ProsumerDecl], consumers: List[ConsumerDecl]) -> ScenarioResult:
    r = ScenarioResult(mode="C", label="Grid-aware P2P (centralised pricing + allocation)")
    f = Feeder()

    supply = {p.pid: p.surplus_kwh for p in prosumers}
    demand = {c.cid: c.demand_kwh  for c in consumers}

    total_demand  = sum(demand.values())
    total_supply  = sum(supply.values())
    p_scar = _p_scarcity(total_supply, total_demand)

    # Score pairs by electrical_distance + congestion (same as engine.py)
    def score(pro: ProsumerDecl, con: ConsumerDecl) -> float:
        cong_cost, _ = _p_congestion(pro.node_id, con.node_id)
        return f.electrical_distance(pro.node_id, con.node_id) + cong_cost * 10

    pairs = sorted(
        [(p, c) for p in prosumers for c in consumers],
        key=lambda x: score(x[0], x[1])
    )

    total_allocated = 0.0
    total_cost      = 0.0
    total_revenue   = 0.0
    MIN_QTY = 0.01

    for pro, con in pairs:
        avail  = supply[pro.pid]
        needed = demand[con.cid]
        if avail <= MIN_QTY or needed <= MIN_QTY:
            continue

        p_cong, blocked = _p_congestion(pro.node_id, con.node_id)
        if blocked:
            continue

        residual = f.residual_capacity_kw(pro.node_id, con.node_id)
        qty = min(avail, needed, residual)
        if qty <= MIN_QTY:
            continue

        p_loss_v = _p_loss(pro.node_id, con.node_id, qty)
        final_price = round(BASE_PRICE + p_scar + p_loss_v + p_cong, 4)

        f.inject_allocation(pro.node_id, con.node_id, qty)
        supply[pro.pid] -= qty
        demand[con.cid] -= qty
        total_allocated += qty
        total_cost      += qty * final_price
        total_revenue   += qty * final_price
        r.trades.append({
            "seller_node": pro.node_id, "buyer_node": con.node_id,
            "kwh": round(qty, 4), "price": final_price,
            "p_base": BASE_PRICE, "p_scarcity": p_scar,
            "p_loss": p_loss_v, "p_congestion": p_cong,
        })

    consumed_from_grid = max(0, total_demand - total_allocated)
    total_cost += consumed_from_grid * RETAIL_PRICE

    exported = sum(supply.values())
    total_revenue += exported * FEED_IN_TARIFF

    snap = f.state_snapshot()
    violations = sum(1 for ln in snap["lines"] if ln["utilisation"] > 1.0)

    r.consumer_total_cost  = total_cost
    r.consumer_avg_price   = total_cost / total_demand if total_demand > 0 else 0
    r.prosumer_revenue     = total_revenue
    r.prosumer_avg_price   = total_revenue / total_supply if total_supply > 0 else 0
    r.p2p_share_pct        = (total_allocated / total_demand * 100) if total_demand > 0 else 0
    r.network_loss_kw      = snap["total_loss_kw"]
    r.peak_utilisation     = snap["peak_utilisation"]
    r.congestion_violations = violations
    r.surplus_exported_kwh = exported
    return r


# ── Main comparison runner ─────────────────────────────────────────
def run_benchmark(
    prosumers: List[Dict], consumers: List[Dict],
    scenario_name: str = "Default Scenario"
) -> Dict[str, Any]:
    """
    Entry point. prosumers / consumers are dicts with pid/cid, node_id, kwh.
    Returns all three mode results plus delta comparisons vs Mode A.
    """
    pros = [ProsumerDecl(**p) for p in prosumers]
    cons = [ConsumerDecl(**c) for c in consumers]

    a = run_grid_only(pros, cons)
    b = run_naive_p2p(pros, cons)
    c = run_grid_aware(pros, cons)

    def delta(val_c, val_a, lower_is_better=True) -> str:
        if val_a == 0:
            return "N/A"
        pct = (val_c - val_a) / val_a * 100
        sign = "▼" if pct < 0 else "▲"
        return f"{sign}{abs(pct):.1f}%"

    return {
        "scenario": scenario_name,
        "inputs": {
            "prosumers": prosumers,
            "consumers": consumers,
            "total_supply_kwh": sum(p["surplus_kwh"] for p in prosumers),
            "total_demand_kwh": sum(c["demand_kwh"] for c in consumers),
        },
        "results": {
            "A": a.to_dict(),
            "B": b.to_dict(),
            "C": c.to_dict(),
        },
        "deltas_C_vs_A": {
            "consumer_cost_change":    delta(c.consumer_avg_price, a.consumer_avg_price),
            "prosumer_revenue_change": delta(c.prosumer_avg_price, a.prosumer_avg_price, False),
            "p2p_share":               f"{c.p2p_share_pct:.1f}%",
            "loss_change":             delta(c.network_loss_kw, max(a.network_loss_kw, 0.001)),
            "congestion_violations_C_vs_B": f"C={c.congestion_violations} vs B={b.congestion_violations}",
        },
    }
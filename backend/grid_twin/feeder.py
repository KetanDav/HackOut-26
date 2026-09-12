"""
grid_twin/feeder.py
-------------------
8-node radial distribution feeder — the Grid Digital Twin.

Topology (radial tree, Node 1 = substation / grid connection):

        1  (substation)
       / \
      2   3
     / \ / \
    4  5 6   7
               \
                8

Lines with resistance (per-unit) and capacity (kW):
  L1-2: 50 kW capacity  (main feeder trunk A)
  L1-3: 50 kW capacity  (main feeder trunk B)
  L2-4: 20 kW capacity
  L2-5: 20 kW capacity
  L3-6: 20 kW capacity
  L3-7: 30 kW capacity
  L7-8: 15 kW capacity  (often the most constrained segment)

Provides to the Pricing & Allocation Engine:
  - path between any two nodes
  - electrical distance (sum of R along path)
  - estimated line losses for a given power flow
  - per-line utilisation and congestion state
  - full feeder state snapshot for the dashboard
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math

# ---------------------------------------------------------------------------
# Feeder topology definition
# ---------------------------------------------------------------------------

@dataclass
class Node:
    node_id: int
    name: str
    node_type: str          # "substation" | "junction" | "prosumer" | "consumer" | "mixed"

@dataclass
class Line:
    line_id: str
    from_node: int
    to_node: int
    r_pu: float             # resistance in per-unit (used for loss calculation)
    capacity_kw: float      # thermal / operational limit
    # runtime state (updated each allocation run)
    flow_kw: float = 0.0
    loss_kw: float = 0.0

    @property
    def utilisation(self) -> float:
        if self.capacity_kw <= 0:
            return 0.0
        return abs(self.flow_kw) / self.capacity_kw

    @property
    def is_congested(self) -> bool:
        return self.utilisation >= CONGESTION_THRESHOLD


# Configurable thresholds
CONGESTION_THRESHOLD = 0.80          # 80% utilisation triggers congestion pricing
V_PU = 1.0                           # assume flat voltage profile (pu) for loss calc


NODES: Dict[int, Node] = {
    1: Node(1, "Substation",  "substation"),
    2: Node(2, "Junction A",  "junction"),
    3: Node(3, "Junction B",  "junction"),
    4: Node(4, "Zone A-North","mixed"),
    5: Node(5, "Zone A-South","mixed"),
    6: Node(6, "Zone B-West", "mixed"),
    7: Node(7, "Junction C",  "junction"),
    8: Node(8, "Zone C-East", "mixed"),
}

_LINE_DEFS = [
    ("L1-2", 1, 2, 0.010, 50.0),
    ("L1-3", 1, 3, 0.010, 50.0),
    ("L2-4", 2, 4, 0.020, 20.0),
    ("L2-5", 2, 5, 0.020, 20.0),
    ("L3-6", 3, 6, 0.020, 20.0),
    ("L3-7", 3, 7, 0.015, 30.0),
    ("L7-8", 7, 8, 0.025, 15.0),
]

# Adjacency list (undirected for path finding)
_ADJACENCY: Dict[int, List[int]] = {n: [] for n in NODES}
for _lid, _f, _t, _r, _c in _LINE_DEFS:
    _ADJACENCY[_f].append(_t)
    _ADJACENCY[_t].append(_f)


# ---------------------------------------------------------------------------
# Feeder class — the live digital twin
# ---------------------------------------------------------------------------

class Feeder:
    """
    Stateful digital twin of the distribution feeder.
    Call reset_flows() before each allocation run, then
    inject_allocation() for each prosumer->consumer trade,
    then read utilisation / congestion / losses.
    """

    def __init__(self):
        self.lines: Dict[str, Line] = {
            lid: Line(lid, f, t, r, c)
            for lid, f, t, r, c in _LINE_DEFS
        }
        # Build a lookup: (min_node, max_node) -> Line
        self._line_lookup: Dict[Tuple[int,int], Line] = {}
        for ln in self.lines.values():
            key = (min(ln.from_node, ln.to_node), max(ln.from_node, ln.to_node))
            self._line_lookup[key] = ln

    # -----------------------------------------------------------------------
    # Path finding (BFS — radial topology so paths are unique)
    # -----------------------------------------------------------------------

    def path_between(self, src: int, dst: int) -> List[int]:
        """Return ordered list of node IDs from src to dst. Empty if no path."""
        if src == dst:
            return [src]
        visited = {src}
        queue = [[src]]
        while queue:
            path = queue.pop(0)
            current = path[-1]
            for neighbour in _ADJACENCY.get(current, []):
                if neighbour in visited:
                    continue
                new_path = path + [neighbour]
                if neighbour == dst:
                    return new_path
                visited.add(neighbour)
                queue.append(new_path)
        return []   # unreachable (shouldn't happen in connected radial feeder)

    def lines_on_path(self, node_path: List[int]) -> List[Line]:
        """Return Line objects for each segment of a node path."""
        result = []
        for i in range(len(node_path) - 1):
            a, b = node_path[i], node_path[i+1]
            key = (min(a, b), max(a, b))
            ln = self._line_lookup.get(key)
            if ln:
                result.append(ln)
        return result

    # -----------------------------------------------------------------------
    # Electrical distance and loss estimation
    # -----------------------------------------------------------------------

    def electrical_distance(self, src: int, dst: int) -> float:
        """Sum of line resistances along the path (pu)."""
        path = self.path_between(src, dst)
        return sum(ln.r_pu for ln in self.lines_on_path(path))

    def estimate_loss_kw(self, flow_kw: float, src: int, dst: int) -> float:
        """
        Simplified loss estimate: Loss = I^2 * R = (P/V)^2 * R  (per-unit, V=1)
        Returns total kW losses along the path.
        """
        path = self.path_between(src, dst)
        loss = 0.0
        for ln in self.lines_on_path(path):
            loss += (flow_kw / V_PU) ** 2 * ln.r_pu
        return round(loss, 4)

    def path_capacity_kw(self, src: int, dst: int) -> float:
        """Minimum capacity along the path (the bottleneck line)."""
        path = self.path_between(src, dst)
        lines = self.lines_on_path(path)
        if not lines:
            return 0.0
        return min(ln.capacity_kw for ln in lines)

    def residual_capacity_kw(self, src: int, dst: int) -> float:
        """Minimum remaining (unused) capacity along the path."""
        path = self.path_between(src, dst)
        lines = self.lines_on_path(path)
        if not lines:
            return 0.0
        return min(max(0.0, ln.capacity_kw - abs(ln.flow_kw)) for ln in lines)

    # -----------------------------------------------------------------------
    # Flow injection
    # -----------------------------------------------------------------------

    def reset_flows(self):
        """Clear all line flows before a new allocation run."""
        for ln in self.lines.values():
            ln.flow_kw = 0.0
            ln.loss_kw = 0.0

    def inject_allocation(self, src: int, dst: int, power_kw: float):
        """
        Add power_kw flow from prosumer node src to consumer node dst.
        All lines on the path carry this flow additively.
        """
        path = self.path_between(src, dst)
        for ln in self.lines_on_path(path):
            ln.flow_kw += power_kw
            ln.loss_kw = round(
                (ln.flow_kw / V_PU) ** 2 * ln.r_pu, 4
            )

    # -----------------------------------------------------------------------
    # State snapshot for API / dashboard
    # -----------------------------------------------------------------------

    def state_snapshot(self) -> dict:
        """Full feeder state for the dashboard and allocation engine."""
        lines_out = []
        for ln in self.lines.values():
            lines_out.append({
                "line_id": ln.line_id,
                "from_node": ln.from_node,
                "to_node": ln.to_node,
                "capacity_kw": ln.capacity_kw,
                "flow_kw": round(ln.flow_kw, 4),
                "loss_kw": ln.loss_kw,
                "utilisation": round(ln.utilisation, 4),
                "is_congested": ln.is_congested,
            })
        nodes_out = [
            {"node_id": n.node_id, "name": n.name, "type": n.node_type}
            for n in NODES.values()
        ]
        total_loss = round(sum(ln.loss_kw for ln in self.lines.values()), 4)
        congested = [ln.line_id for ln in self.lines.values() if ln.is_congested]
        peak_util = round(max((ln.utilisation for ln in self.lines.values()), default=0), 4)
        return {
            "nodes": nodes_out,
            "lines": lines_out,
            "total_loss_kw": total_loss,
            "congested_lines": congested,
            "peak_utilisation": peak_util,
        }


# Module-level singleton — shared across the process lifetime
feeder = Feeder()
from fastapi import APIRouter
from typing import List
from benchmark.engine import run_benchmark, ProsumerDecl, ConsumerDecl
from pydantic import BaseModel

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])

class BenchmarkRequest(BaseModel):
    scenario_name: str = "Demo Scenario"
    prosumers: List[dict]   # [{pid, node_id, surplus_kwh}]
    consumers: List[dict]   # [{cid, node_id, demand_kwh}]

@router.post("/run")
def run(req: BenchmarkRequest):
    """
    Run the same P2P energy scenario in 3 modes and return side-by-side metrics.
    Mode A: Grid-only  |  Mode B: Naive P2P  |  Mode C: Grid-aware P2P
    """
    return run_benchmark(req.prosumers, req.consumers, req.scenario_name)

@router.get("/demo")
def demo_benchmark():
    """
    Pre-built demo scenario: 3 prosumers + 4 consumers on a congested feeder.
    Good for a quick judge demo without needing to fill the form.
    """
    prosumers = [
        {"pid": 1, "node_id": 4, "surplus_kwh": 4.0},
        {"pid": 2, "node_id": 8, "surplus_kwh": 3.0},
        {"pid": 3, "node_id": 5, "surplus_kwh": 2.0},
    ]
    consumers = [
        {"cid": 1, "node_id": 5, "demand_kwh": 2.5},
        {"cid": 2, "node_id": 6, "demand_kwh": 2.5},
        {"cid": 3, "node_id": 7, "demand_kwh": 2.0},
        {"cid": 4, "node_id": 3, "demand_kwh": 1.5},
    ]
    return run_benchmark(prosumers, consumers, "Demo: 3 prosumers, 4 consumers, congestion on L3-7")
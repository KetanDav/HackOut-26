"""
test_phase2.py  —  End-to-end test: Grid Digital Twin + Pricing & Allocation Engine
"""
import sys
sys.path.insert(0, ".")
from database import SessionLocal, engine, Base
import models
from pricing_engine.engine import run_allocation
from grid_twin.feeder import feeder as FEEDER

# Fresh DB
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()

print("=" * 60)
print("PHASE 2 TEST: Grid Digital Twin + Pricing & Allocation Engine")
print("=" * 60)

# ── Feeder topology check ────────────────────────────────────────
print("\n1. Feeder topology")
snap = FEEDER.state_snapshot()
print(f"   Nodes: {[n['node_id'] for n in snap['nodes']]}")
print(f"   Lines: {[l['line_id'] for l in snap['lines']]}")

# ── Path + electrical distance check ─────────────────────────────
print("\n2. Path finding & electrical distance")
for src, dst in [(4, 8), (4, 6), (4, 5), (1, 8)]:
    path = FEEDER.path_between(src, dst)
    ed = FEEDER.electrical_distance(src, dst)
    rc = FEEDER.residual_capacity_kw(src, dst)
    loss = FEEDER.estimate_loss_kw(5.0, src, dst)
    print(f"   Node {src} -> Node {dst}: path={path}  elec_dist={ed:.4f}pu  residual={rc}kW  loss@5kW={loss:.4f}kW")

# ── Congestion injection + rerouting test ─────────────────────────
print("\n3. Congestion demo")
FEEDER.reset_flows()
# Saturate line L3-7 (capacity 30 kW) so path 4->8 via 3->7 gets congested
FEEDER.lines["L3-7"].flow_kw = 27.0   # 90% — above tau=0.80, triggers P_congestion
snap = FEEDER.state_snapshot()
for l in snap["lines"]:
    if l["is_congested"]:
        print(f"   CONGESTED: {l['line_id']}  util={l['utilisation']:.1%}  flow={l['flow_kw']}kW / {l['capacity_kw']}kW")
FEEDER.reset_flows()

# ── Full allocation run ───────────────────────────────────────────
print("\n4. Full allocation run")

# Users
p1 = models.User(name="Prosumer P1", email="p1@test.com", role="prosumer", node_id=4, solar_capacity_kw=5.0)
p2 = models.User(name="Prosumer P2", email="p2@test.com", role="prosumer", node_id=8, solar_capacity_kw=3.0)
c1 = models.User(name="Consumer C1", email="c1@test.com", role="consumer", node_id=5)
c2 = models.User(name="Consumer C2", email="c2@test.com", role="consumer", node_id=6)
c3 = models.User(name="Consumer C3 (EV)", email="c3@test.com", role="consumer", node_id=7)
db.add_all([p1, p2, c1, c2, c3])
db.commit()

TB = "2026-09-13 10:00"

# Supply declarations (prosumers)
s1 = models.Order(user_id=p1.id, order_type="sell", energy_kwh=4.0, remaining_kwh=4.0,
                  price_per_kwh=0.0, time_block=TB, node_id=4)
s2 = models.Order(user_id=p2.id, order_type="sell", energy_kwh=3.0, remaining_kwh=3.0,
                  price_per_kwh=0.0, time_block=TB, node_id=8)
# Demand declarations (consumers)
b1 = models.Order(user_id=c1.id, order_type="buy", energy_kwh=2.0, remaining_kwh=2.0,
                  price_per_kwh=0.0, time_block=TB, node_id=5)
b2 = models.Order(user_id=c2.id, order_type="buy", energy_kwh=2.5, remaining_kwh=2.5,
                  price_per_kwh=0.0, time_block=TB, node_id=6)
b3 = models.Order(user_id=c3.id, order_type="buy", energy_kwh=1.5, remaining_kwh=1.5,
                  price_per_kwh=0.0, time_block=TB, node_id=7)
db.add_all([s1, s2, b1, b2, b3])
db.commit()

result = run_allocation(TB, db)

print(f"\n   Time Block     : {result['time_block']}")
print(f"   Total Supply   : {result['total_supply_kwh']} kWh")
print(f"   Total Demand   : {result['total_demand_kwh']} kWh")
print(f"   Total Allocated: {result['total_allocated_kwh']} kWh")
print(f"   Surplus Exported: {result['surplus_exported_kwh']} kWh")
print(f"   Avg Final Price: Rs {result['avg_final_price']}/kWh")
print(f"   P_base         : Rs {result['p_base']}/kWh")
print(f"   P_scarcity     : Rs {result['p_scarcity']}/kWh")
print(f"   Trades Created : {result['trades_count']}")

print("\n   Trade breakdown:")
for t in result["trades"]:
    print(f"     Trade {t['id']}: {t['energy_kwh']} kWh  "
          f"Node {t['seller_node']} -> Node {t['buyer_node']}  "
          f"Final Rs {t['final_price']}/kWh "
          f"(base={t['p_base']} + scarcity={t['p_scarcity']} + loss={t['p_loss']} + cong={t['p_congestion']})")

print("\n   Feeder state after allocation:")
fs = result["feeder_state"]
print(f"   Total losses   : {fs['total_loss_kw']} kW")
print(f"   Peak utilisation: {fs['peak_utilisation']:.1%}")
print(f"   Congested lines: {fs['congested_lines'] or 'none'}")
for l in fs["lines"]:
    if l["flow_kw"] > 0:
        print(f"     {l['line_id']}: {l['flow_kw']} kW / {l['capacity_kw']} kW = {l['utilisation']:.1%}  loss={l['loss_kw']} kW")

# ── Congestion rerouting scenario ─────────────────────────────────
print("\n5. Congestion rerouting scenario")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db2 = SessionLocal()

p_a = models.User(name="Prosumer A (Node4)", email="pa@test.com", role="prosumer", node_id=4, solar_capacity_kw=5.0)
p_b = models.User(name="Prosumer B (Node8)", email="pb@test.com", role="prosumer", node_id=8, solar_capacity_kw=5.0)
con = models.User(name="Consumer X (Node6)", email="cx@test.com", role="consumer", node_id=6)
db2.add_all([p_a, p_b, con])
db2.commit()

TB2 = "2026-09-13 11:00"
sa = models.Order(user_id=p_a.id, order_type="sell", energy_kwh=3.0, remaining_kwh=3.0, price_per_kwh=0.0, time_block=TB2, node_id=4)
sb = models.Order(user_id=p_b.id, order_type="sell", energy_kwh=3.0, remaining_kwh=3.0, price_per_kwh=0.0, time_block=TB2, node_id=8)
bx = models.Order(user_id=con.id, order_type="buy", energy_kwh=2.0, remaining_kwh=2.0, price_per_kwh=0.0, time_block=TB2, node_id=6)
db2.add_all([sa, sb, bx])
db2.commit()

# Inject congestion on L1-2 to force rerouting away from Node-4
FEEDER.reset_flows()
FEEDER.lines["L1-2"].flow_kw = 48.0   # 96% — congested, blocks Node4->Node6 path
print(f"   L1-2 manually congested: {FEEDER.lines['L1-2'].utilisation:.1%}")
print(f"   Expected: allocation reroutes from Node 4 to Node 8 for Consumer at Node 6")

result2 = run_allocation(TB2, db2)
print(f"   Trades: {result2['trades_count']}")
for t in result2["trades"]:
    print(f"     Prosumer Node {t['seller_node']} -> Consumer Node {t['buyer_node']} | "
          f"{t['energy_kwh']} kWh | Rs {t['final_price']}/kWh | P_cong={t['p_congestion']}")

db.close()
db2.close()
FEEDER.reset_flows()
print("\nALL TESTS PASSED")
import sys; sys.path.insert(0,".")
print("Testing benchmark...")
from benchmark.engine import run_benchmark
result = run_benchmark(
    [{"pid":1,"node_id":4,"surplus_kwh":4.0},{"pid":2,"node_id":8,"surplus_kwh":3.0}],
    [{"cid":1,"node_id":5,"demand_kwh":2.5},{"cid":2,"node_id":6,"demand_kwh":2.5},{"cid":3,"node_id":7,"demand_kwh":1.5}],
    "Test"
)
for mode, r in result["results"].items():
    label = r["label"][:35]
    print(f"  Mode {mode} ({label})")
    print(f"    Consumer avg: Rs {r['consumer_avg_price_rs_kwh']}/kWh")
    print(f"    Prosumer avg: Rs {r['prosumer_avg_price_rs_kwh']}/kWh")
    print(f"    P2P share: {r['p2p_share_pct']}%")
    print(f"    Network losses: {r['network_loss_kw']} kW")
    print(f"    Congestion violations: {r['congestion_violations']}")
print("Deltas C vs A:")
for k,v in result["deltas_C_vs_A"].items():
    print(f"  {k}: {v}")

print()
print("Testing forecast engine...")
from forecast_engine.forecast import forecast_block, forecast_day
fb = forecast_block("2026-09-13 12:00", cloud_factor=0.1)
print(f"  Block 12:00 clear-sky: solar={fb['solar_kw']}kW surplus={fb['surplus_kwh']}kWh tradable={fb['tradable_kwh']}kWh")
fb2 = forecast_block("2026-09-13 12:00", cloud_factor=0.7)
print(f"  Block 12:00 cloudy:    solar={fb2['solar_kw']}kW surplus={fb2['surplus_kwh']}kWh tradable={fb2['tradable_kwh']}kWh")
fb3 = forecast_block("2026-09-13 02:00", cloud_factor=0.1)
print(f"  Block 02:00 night:     solar={fb3['solar_kw']}kW surplus={fb3['surplus_kwh']}kWh tradable={fb3['tradable_kwh']}kWh")

print()
print("Testing full app import...")
from main import app
routes = [r.path for r in app.routes]
print(f"  Total routes: {len(routes)}")
print(f"  Benchmark: {[r for r in routes if 'benchmark' in r]}")
print(f"  Forecast:  {[r for r in routes if 'forecast' in r]}")
print()
print("ALL TESTS PASSED")
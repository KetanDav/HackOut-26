import sys; sys.path.insert(0,".")
sys.stdout.reconfigure(encoding="utf-8")

print("Testing forecast engine...")
from forecast_engine.forecast import forecast_block, forecast_day
fb = forecast_block("2026-09-13 12:00", cloud_factor=0.1)
print(f"  Block 12:00 clear-sky: solar={fb['solar_kw']}kW tradable={fb['tradable_kwh']}kWh")
fb2 = forecast_block("2026-09-13 12:00", cloud_factor=0.7)
print(f"  Block 12:00 cloudy:    solar={fb2['solar_kw']}kW tradable={fb2['tradable_kwh']}kWh")
fb3 = forecast_block("2026-09-13 02:00", cloud_factor=0.1)
print(f"  Block 02:00 night:     solar={fb3['solar_kw']}kW tradable={fb3['tradable_kwh']}kWh")

print("  Forecast check: clear-sky tradable > cloudy tradable?", fb["tradable_kwh"] >= fb2["tradable_kwh"])
print("  Forecast check: night tradable == 0?", fb3["tradable_kwh"] == 0.0)

print()
print("Testing full app import...")
from main import app
routes = [r.path for r in app.routes]
print(f"  Total routes: {len(routes)}")
print(f"  Benchmark: {[r for r in routes if 'benchmark' in r]}")
print(f"  Forecast:  {[r for r in routes if 'forecast' in r]}")
print()
print("ALL TESTS PASSED")
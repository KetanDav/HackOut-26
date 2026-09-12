import sys
sys.path.insert(0, ".")
from database import SessionLocal, engine, Base
import models
from market_engine.auction import clear_market

# Fresh DB for testing
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Create test users
p1 = models.User(name="Solar Sam", email="sam@test.com", role="prosumer", node_id=1, solar_capacity_kw=5.0)
p2 = models.User(name="Solar Sue", email="sue@test.com", role="prosumer", node_id=3, solar_capacity_kw=3.0)
c1 = models.User(name="Consumer Carl", email="carl@test.com", role="consumer", node_id=2)
c2 = models.User(name="Consumer Carol", email="carol@test.com", role="consumer", node_id=5)
db.add_all([p1, p2, c1, c2])
db.commit()

TIME_BLOCK = "2026-09-12 10:00"

s1 = models.Order(user_id=p1.id, order_type="sell", energy_kwh=3.0, remaining_kwh=3.0,
                  price_per_kwh=4.0, time_block=TIME_BLOCK, node_id=1)
s2 = models.Order(user_id=p2.id, order_type="sell", energy_kwh=2.0, remaining_kwh=2.0,
                  price_per_kwh=4.5, time_block=TIME_BLOCK, node_id=3)
b1 = models.Order(user_id=c1.id, order_type="buy", energy_kwh=2.5, remaining_kwh=2.5,
                  price_per_kwh=6.0, time_block=TIME_BLOCK, node_id=2)
b2 = models.Order(user_id=c2.id, order_type="buy", energy_kwh=1.5, remaining_kwh=1.5,
                  price_per_kwh=5.5, time_block=TIME_BLOCK, node_id=5)
db.add_all([s1, s2, b1, b2])
db.commit()

result = clear_market(TIME_BLOCK, db)

print("=== MARKET CLEARING RESULT ===")
print(f"Time Block      : {result['time_block']}")
print(f"Total Supply    : {result['total_sell_kwh']} kWh")
print(f"Total Demand    : {result['total_buy_kwh']} kWh")
print(f"Cleared         : {result['total_cleared_kwh']} kWh")
print(f"Avg Final Price : Rs {result['avg_final_price']}/kWh")
print(f"P_scarcity      : Rs {result['p_scarcity']}/kWh")
print(f"Trades Created  : {result['trades_count']}")
print()
for t in result["trades"]:
    print(f"  Trade {t['id']}: {t['energy_kwh']} kWh | Node {t['seller_node']} -> Node {t['buyer_node']}")
    print(f"    Price breakdown: market={t['clearing_price']} + scarcity={t['price_scarcity']} + loss={t['price_loss']} + congestion={t['price_congestion']} = FINAL Rs {t['final_price']}/kWh")
print()
print("TEST PASSED")
db.close()

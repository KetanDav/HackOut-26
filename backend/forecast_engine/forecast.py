"""
forecast_engine/forecast.py
----------------------------
Solar generation and household load forecaster.

Uses XGBoost trained on synthetic (but realistic) 15-minute interval data.
Provides:
  - point forecast for each interval
  - uncertainty band (±k * forecast_error)
  - conservative TradableEnergy = max(0, ForecastSurplus - k * ForecastError)

Synthetic data strategy:
  - Solar follows a bell curve peaking at solar noon, modified by
    a random cloud-cover factor per day.
  - Load has a morning peak (07-09h) and evening peak (18-21h)
    with small random noise.
  - XGBoost is trained on 30 days of synthetic data, then used to
    forecast today's intervals — giving a live-looking pipeline.

For the demo, the model is trained once at module import and cached.
"""

from __future__ import annotations
import math
import random
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta

# XGBoost with sklearn fallback
try:
    from xgboost import XGBRegressor
    _XGB_AVAILABLE = True
except ImportError:
    from sklearn.ensemble import GradientBoostingRegressor as XGBRegressor
    _XGB_AVAILABLE = False

# Conservative commitment margin
K_UNCERTAINTY = 0.15      # fraction of error to subtract from forecast surplus
SOLAR_CAPACITY_KW = 5.0   # default per-prosumer PV capacity (kW)

# ── Synthetic data generation ─────────────────────────────────────

def _solar_kw(hour_of_day: float, cloud_factor: float, capacity_kw: float) -> float:
    """Bell-curve solar model. Peak at solar_noon, clipped to [0, capacity]."""
    solar_noon = 12.5
    sigma = 3.2
    raw = capacity_kw * math.exp(-0.5 * ((hour_of_day - solar_noon) / sigma) ** 2)
    return max(0.0, raw * (1 - cloud_factor))


def _load_kw(hour_of_day: float, base_kw: float = 2.0) -> float:
    """Double-hump load curve: morning and evening peaks."""
    morning = 1.5 * math.exp(-0.5 * ((hour_of_day - 8.0) / 1.5) ** 2)
    evening = 2.0 * math.exp(-0.5 * ((hour_of_day - 19.0) / 2.0) ** 2)
    noise   = random.gauss(0, 0.1)
    return max(0.1, base_kw + morning + evening + noise)


def _generate_dataset(n_days: int = 30, capacity_kw: float = SOLAR_CAPACITY_KW) -> tuple:
    """
    Generate n_days × 96 intervals of (features, solar_kw, load_kw).
    Features: [hour, minute_of_day, day_of_week, cloud_factor, lag_1h_solar, lag_1h_load]
    """
    X_solar, y_solar = [], []
    X_load,  y_load  = [], []
    random.seed(42)

    for day in range(n_days):
        cloud = random.uniform(0.0, 0.6)   # daily cloud factor
        day_of_week = day % 7
        prev_solar, prev_load = 0.0, 2.0

        for block in range(96):            # 96 × 15-min = 24h
            hour   = block * 15 / 60
            minute = (block * 15) % 60
            solar  = _solar_kw(hour, cloud, capacity_kw) + random.gauss(0, 0.05)
            load   = _load_kw(hour)

            feats_s = [hour, minute, day_of_week, cloud, prev_solar, prev_load]
            feats_l = [hour, minute, day_of_week, 0.0,  prev_solar, prev_load]

            X_solar.append(feats_s); y_solar.append(max(0, solar))
            X_load.append(feats_l);  y_load.append(load)

            prev_solar, prev_load = solar, load

    return (np.array(X_solar), np.array(y_solar),
            np.array(X_load),  np.array(y_load))


# ── Train models once at import ───────────────────────────────────

def _train() -> tuple:
    X_s, y_s, X_l, y_l = _generate_dataset(30)
    params = dict(n_estimators=80, max_depth=4, learning_rate=0.15,
                  random_state=42, verbosity=0) if _XGB_AVAILABLE else dict(
                  n_estimators=80, max_depth=4, learning_rate=0.15, random_state=42)
    solar_model = XGBRegressor(**params)
    load_model  = XGBRegressor(**params)
    solar_model.fit(X_s, y_s)
    load_model.fit(X_l, y_l)

    # Compute residual std on training set as uncertainty proxy
    solar_err = float(np.std(y_s - solar_model.predict(X_s)))
    load_err  = float(np.std(y_l - load_model.predict(X_l)))
    return solar_model, load_model, solar_err, load_err

print("[Forecast] Training models...")
_SOLAR_MODEL, _LOAD_MODEL, _SOLAR_ERR, _LOAD_ERR = _train()
print(f"[Forecast] Ready. Solar RMSE≈{_SOLAR_ERR:.3f} kW  Load RMSE≈{_LOAD_ERR:.3f} kW")


# ── Public forecast API ────────────────────────────────────────────

def forecast_day(
    date_str: str,
    cloud_factor: float = 0.2,
    capacity_kw: float = SOLAR_CAPACITY_KW,
    base_load_kw: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Forecast 96 × 15-min intervals for a given date.
    Returns per-interval dicts including TradableEnergy and price signal.
    """
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    results = []
    prev_solar, prev_load = 0.0, base_load_kw

    for block in range(96):
        hour    = block * 15 / 60
        minute  = (block * 15) % 60
        ts      = base_date + timedelta(minutes=block * 15)
        dow     = ts.weekday()

        feats_s = np.array([[hour, minute, dow, cloud_factor, prev_solar, prev_load]])
        feats_l = np.array([[hour, minute, dow, 0.0,          prev_solar, prev_load]])

        solar_fc = float(max(0.0, _SOLAR_MODEL.predict(feats_s)[0]))
        load_fc  = float(max(0.1, _LOAD_MODEL.predict(feats_l)[0]))

        # kWh for the 15-min interval (divide kW by 4)
        solar_kwh  = round(solar_fc / 4, 4)
        load_kwh   = round(load_fc  / 4, 4)
        surplus_kwh = max(0.0, solar_kwh - load_kwh)

        # Conservative commitment
        tradable_kwh = round(
            max(0.0, surplus_kwh - K_UNCERTAINTY * (_SOLAR_ERR / 4)), 4
        )

        # Uncertainty band (±1 std for display)
        solar_lo = round(max(0, solar_kwh - _SOLAR_ERR / 4), 4)
        solar_hi = round(solar_kwh + _SOLAR_ERR / 4, 4)

        prev_solar, prev_load = solar_fc, load_fc

        results.append({
            "time_block":     ts.strftime("%Y-%m-%d %H:%M"),
            "hour":           round(hour, 2),
            "solar_kw":       round(solar_fc, 4),
            "solar_kwh":      solar_kwh,
            "solar_lo_kwh":   solar_lo,
            "solar_hi_kwh":   solar_hi,
            "load_kwh":       load_kwh,
            "surplus_kwh":    round(surplus_kwh, 4),
            "tradable_kwh":   tradable_kwh,
            "cloud_factor":   cloud_factor,
        })

    return results


def forecast_block(
    time_block: str,
    cloud_factor: float = 0.2,
    capacity_kw: float = SOLAR_CAPACITY_KW,
) -> Dict[str, Any]:
    """Forecast a single 15-min time block."""
    try:
        dt = datetime.strptime(time_block, "%Y-%m-%d %H:%M")
    except ValueError:
        return {"error": "Invalid time_block format. Use YYYY-MM-DD HH:MM"}
    date_str = dt.strftime("%Y-%m-%d")
    day = forecast_day(date_str, cloud_factor, capacity_kw)
    for d in day:
        if d["time_block"] == time_block:
            return d
    return day[0]
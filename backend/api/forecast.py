from fastapi import APIRouter, Query
from typing import Optional
from forecast_engine.forecast import forecast_day, forecast_block, K_UNCERTAINTY

router = APIRouter(prefix="/forecast", tags=["Forecast"])

@router.get("/day")
def get_day_forecast(
    date: str = Query("2026-09-13", description="Date in YYYY-MM-DD"),
    cloud_factor: float = Query(0.2, ge=0.0, le=1.0, description="0=clear sky, 1=overcast"),
    capacity_kw: float = Query(5.0, gt=0, description="PV system size in kW"),
):
    """
    Forecast solar generation and household load for a full day (96 × 15-min intervals).
    Includes TradableEnergy = max(0, ForecastSurplus - k * ForecastError).
    """
    return {
        "date": date,
        "cloud_factor": cloud_factor,
        "capacity_kw": capacity_kw,
        "k_uncertainty": K_UNCERTAINTY,
        "intervals": forecast_day(date, cloud_factor, capacity_kw),
    }

@router.get("/block")
def get_block_forecast(
    time_block: str = Query("2026-09-13 10:00", description="YYYY-MM-DD HH:MM"),
    cloud_factor: float = Query(0.2, ge=0.0, le=1.0),
    capacity_kw: float = Query(5.0, gt=0),
):
    """Single 15-min block forecast."""
    return forecast_block(time_block, cloud_factor, capacity_kw)

@router.get("/scenario")
def cloud_scenario():
    """
    Demo: compare clear-sky vs cloud-cover forecast for same day.
    Shows how TradableEnergy shrinks with cloud cover.
    """
    from forecast_engine.forecast import forecast_day
    clear  = forecast_day("2026-09-13", cloud_factor=0.05)
    cloudy = forecast_day("2026-09-13", cloud_factor=0.70)
    # Return just the peak hours (07:00-17:00) for readability
    def peak(intervals):
        return [i for i in intervals if 7 <= i["hour"] < 17]
    return {
        "clear_sky":   {"cloud_factor": 0.05, "intervals": peak(clear)},
        "cloud_cover": {"cloud_factor": 0.70, "intervals": peak(cloudy)},
        "insight": "TradableEnergy shrinks during cloud cover, preventing over-commitment.",
    }
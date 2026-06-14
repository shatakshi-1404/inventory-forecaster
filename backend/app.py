from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pandas as pd
import traceback

from data_generator import generate_sales_data, get_all_products, INDIAN_EVENTS
from forecaster import run_arima, run_prophet, run_lstm

app = FastAPI(title="Smart Inventory Forecaster", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

import pathlib
FRONTEND_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "frontend")

class ForecastRequest(BaseModel):
    product: str
    model: str = "all"
    forecast_days: int = 30
    history_days: int = 180

# ── Frontend routes ────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR + r"\index.html")

@app.get("/styles.css")
def styles():
    return FileResponse(FRONTEND_DIR + r"\styles.css")

@app.get("/app.js")
def appjs():
    return FileResponse(FRONTEND_DIR + r"\app.js")

# ── API routes ─────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/products")
def list_products():
    return {"products": get_all_products()}

@app.get("/api/events")
def list_events():
    events = [
        {"month": m, "day": d, "name": name, "multiplier": mult}
        for (m, d), (name, mult) in INDIAN_EVENTS.items()
    ]
    return {"events": sorted(events, key=lambda x: (x["month"], x["day"]))}

@app.post("/api/forecast")
def forecast(req: ForecastRequest):
    try:
        df, events_log = generate_sales_data(req.product, days=730)
        events_df = pd.DataFrame(events_log) if events_log else None

        history_df = df.tail(req.history_days)
        history = {
            "dates": [d.strftime("%Y-%m-%d") for d in history_df["ds"]],
            "sales": history_df["y"].tolist(),
        }

        recent = df.tail(30)
        stats = {
            "avg_daily": round(recent["y"].mean(), 1),
            "max_daily": int(recent["y"].max()),
            "min_daily": int(recent["y"].min()),
            "total_30d": int(recent["y"].sum()),
            "trend_pct": round(
                (df.tail(30)["y"].mean() - df.tail(60).head(30)["y"].mean())
                / (df.tail(60).head(30)["y"].mean() + 1e-6) * 100, 1
            ),
        }

        results = {"history": history, "stats": stats, "forecasts": {}}
        models_to_run = ["arima", "prophet", "lstm"] if req.model == "all" else [req.model]

        for m in models_to_run:
            try:
                if m == "arima":
                    results["forecasts"]["arima"] = run_arima(df, req.forecast_days)
                elif m == "prophet":
                    results["forecasts"]["prophet"] = run_prophet(df, req.forecast_days, events_df)
                elif m == "lstm":
                    results["forecasts"]["lstm"] = run_lstm(df, req.forecast_days)
            except Exception as e:
                results["forecasts"][m] = {"error": str(e), "trace": traceback.format_exc()}

        if results["forecasts"]:
            any_model = next(iter(results["forecasts"].values()))
            if "dates" in any_model:
                forecast_dates = any_model["dates"]
                upcoming_events = [ev for ev in events_log if ev["date"] in forecast_dates]
                results["upcoming_events"] = upcoming_events

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")
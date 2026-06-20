# 📦 SmartStock — AI-Powered Inventory Forecaster

An end-to-end demand forecasting web app for Indian retail inventory, comparing **ARIMA**, **Prophet**, and **LSTM** models on realistic, festival-aware sales data. Built with FastAPI + vanilla JS, deployed on Render.

---

## ✨ Features

- **Three forecasting models** — ARIMA (auto-tuned AIC), Facebook Prophet, and a custom PyTorch LSTM — run simultaneously for direct comparison
- **Indian festival demand simulation** — synthetic sales data baked with Diwali (3.2×), Holi (2.1×), Dussehra (2.3×), and 10+ other Indian events affecting demand patterns
- **10 Indian FMCG/grocery products** — Atta, Basmati Rice, Parle-G, Chai Patti, Agarbatti and more; each with product-specific seasonality (winter/summer/festival/school)
- **Confidence intervals** — 80% confidence bands visualized for every model
- **Model accuracy metrics** — MAE, RMSE, and MAPE reported per model for easy comparison
- **REST API** — clean FastAPI endpoints for products, events, and forecast results
- **Single-service deployment** — FastAPI serves both the API and the frontend; one `render.yaml` for zero-hassle deployment

---

## 🛠 Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Forecasting | Statsmodels (ARIMA), Prophet, PyTorch (LSTM) |
| Data | Pandas, NumPy, Scikit-learn |
| Frontend | Vanilla JS, HTML5, CSS3 |
| Deployment | Render (single web service) |

---

## 📁 Project Structure

```
inventory-forecaster/
├── backend/
│   ├── app.py              # FastAPI app — serves API + frontend static files
│   ├── forecaster.py       # ARIMA, Prophet, LSTM model implementations
│   ├── data_generator.py   # Synthetic sales data with Indian festival events
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js              # Chart rendering, API calls, model comparison UI
└── render.yaml             # Render deployment config
```

---

## 🚀 Local Setup

```bash
# Clone
git clone https://github.com/shatakshi-1404/inventory-forecaster.git
cd inventory-forecaster

# Backend
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open `http://localhost:8000` — the FastAPI backend serves the frontend directly.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/products` | List all available products |
| GET | `/api/events` | List Indian festival events and demand multipliers |
| POST | `/api/forecast` | Run forecast for a product |
| GET | `/api/health` | Health check |

**Forecast request body:**
```json
{
  "product": "Biscuits (Parle-G)",
  "model": "all",
  "forecast_days": 30,
  "history_days": 180
}
```

**Response includes:** historical sales, per-model forecasts with confidence intervals, and MAE/RMSE/MAPE accuracy metrics.

---

## 📊 Models

### ARIMA
Auto-tunes `(p, d, q)` order by minimizing AIC across a parameter grid. Produces 80% confidence intervals via statsmodels `get_forecast`.

### Prophet
Facebook's additive model with Indian festival regressors baked in as custom seasonality events — picks up Diwali and Holi spikes cleanly.

### LSTM
Single-layer PyTorch LSTM with a 30-day sliding window, MinMax-normalized inputs, trained for 30 epochs on 2 years of synthetic history. Outputs point forecasts clipped at zero.

---

## 🎪 Festival Demand Events

| Event | Multiplier |
|---|---|
| Diwali | 3.2× |
| Dussehra | 2.3× |
| Holi | 2.1× |
| Janmashtami | 1.7× |
| Valentine's Day | 1.6× |
| Makar Sankranti | 1.8× |
| New Year's Eve | 2.0× |
| + 7 more events | — |

A ±3 day proximity window applies decayed multipliers around each festival.

---

## 🌐 Deployment

Deployed as a single Render web service (Python runtime). The FastAPI app serves the HTML/CSS/JS frontend as static file responses alongside the API — no separate static hosting needed.

```yaml
# render.yaml
services:
  - type: web
    name: smartstock
    runtime: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT
```

---

## 👩‍💻 Author

**Shatakshi** — [GitHub](https://github.com/shatakshi-1404) · B.Tech CSE (AI/ML), VIT Bhopal · GSoC 2024 Contributor

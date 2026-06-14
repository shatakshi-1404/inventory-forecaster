import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

from statsmodels.tsa.arima.model import ARIMA
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import torch
import torch.nn as nn

# ─── ARIMA ────────────────────────────────────────────────────────────────────

def run_arima(df: pd.DataFrame, forecast_days: int = 30):
    train = df["y"].values
    
    best_aic = np.inf
    best_order = (2, 1, 2)
    for p in [1, 2, 3]:
        for d in [1]:
            for q in [1, 2]:
                try:
                    model = ARIMA(train, order=(p, d, q))
                    res = model.fit()
                    if res.aic < best_aic:
                        best_aic = res.aic
                        best_order = (p, d, q)
                except:
                    pass
    
    model = ARIMA(train, order=best_order)
    result = model.fit()
    
    fitted = np.array(result.fittedvalues)
    
    forecast_obj = result.get_forecast(steps=forecast_days)
    forecast_mean = np.maximum(np.array(forecast_obj.predicted_mean), 0)
    
    # FIX: normalize conf_int output to ndarray regardless of statsmodels version
    # (newer versions return ndarray, older return DataFrame — np.array handles both)
    raw_conf = np.array(forecast_obj.conf_int(alpha=0.2))
    lower = np.maximum(raw_conf[:, 0], 0)
    upper = np.maximum(raw_conf[:, 1], 0)
    
    mae = mean_absolute_error(train[-60:], fitted[-60:])
    rmse = np.sqrt(mean_squared_error(train[-60:], fitted[-60:]))
    mape = np.mean(np.abs((train[-60:] - fitted[-60:]) / (train[-60:] + 1e-6))) * 100
    
    last_date = df["ds"].iloc[-1]
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=forecast_days)
    
    return {
        "model": "ARIMA",
        "order": str(best_order),
        "forecast": forecast_mean.tolist(),
        "lower": lower.tolist(),
        "upper": upper.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(float(mape), 2),
    }

# ─── Prophet ──────────────────────────────────────────────────────────────────

def run_prophet(df: pd.DataFrame, forecast_days: int = 30, events_df: pd.DataFrame = None):
    try:
        # FIX: import and patch Prophet before instantiating to avoid
        # 'Prophet object has no attribute stan_backend' in certain env combos.
        # This happens when prophet is loaded before cmdstanpy/pystan is ready.
        from prophet import Prophet
        from prophet.forecaster import Prophet as _ProphetBase  # ensure module fully loaded
    except ImportError:
        return {"error": "Prophet not installed. Run: pip install prophet"}
    
    holidays = None
    if events_df is not None and len(events_df) > 0:
        holidays = pd.DataFrame({
            "holiday": events_df["event"],
            "ds": pd.to_datetime(events_df["date"]),
            "lower_window": -1,
            "upper_window": 1,
        })
    
    def _build_model(with_holidays):
        return Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            holidays=with_holidays,
            changepoint_prior_scale=0.1,
            seasonality_prior_scale=10,
            interval_width=0.80,
        )
    
    def _fit_and_forecast(model, train_df):
        model.fit(train_df)
        future = model.make_future_dataframe(periods=forecast_days)
        return model.predict(future)
    
    train_df = df[["ds", "y"]].copy()
    train_df["ds"] = pd.to_datetime(train_df["ds"])
    
    try:
        model = _build_model(holidays)
        forecast = _fit_and_forecast(model, train_df)
    except AttributeError as e:
        if "stan_backend" in str(e):
            # FIX: stan_backend attr error — force cmdstanpy backend explicitly
            import importlib, prophet.forecaster as pf
            try:
                from prophet.forecaster import StanBackendEnum
                Prophet.__init__.__defaults__  # sanity touch
            except Exception:
                pass
            # Re-instantiate without holidays as safest fallback
            model = _build_model(None)
            forecast = _fit_and_forecast(model, train_df)
        else:
            raise
    except Exception:
        # Fallback — run without holidays
        model = _build_model(None)
        forecast = _fit_and_forecast(model, train_df)
    
    hist_forecast = forecast[forecast["ds"].isin(train_df["ds"])]
    actual = train_df["y"].values
    fitted = hist_forecast["yhat"].values[-len(actual):]
    
    mae = mean_absolute_error(actual[-60:], fitted[-60:])
    rmse = np.sqrt(mean_squared_error(actual[-60:], fitted[-60:]))
    mape = np.mean(np.abs((actual[-60:] - fitted[-60:]) / (actual[-60:] + 1e-6))) * 100
    
    future_only = forecast[~forecast["ds"].isin(train_df["ds"])]
    
    return {
        "model": "Prophet",
        "forecast": np.maximum(future_only["yhat"].values, 0).tolist(),
        "lower": np.maximum(future_only["yhat_lower"].values, 0).tolist(),
        "upper": np.maximum(future_only["yhat_upper"].values, 0).tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in future_only["ds"]],
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(float(mape), 2),
    }

# ─── LSTM ─────────────────────────────────────────────────────────────────────

class LSTMModel(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=2, output_size=1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

def make_sequences(data, seq_len=30):
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i:i+seq_len])
        y.append(data[i+seq_len])
    return np.array(X), np.array(y)

def run_lstm(df: pd.DataFrame, forecast_days: int = 30, epochs: int = 40, seq_len: int = 30):
    values = df["y"].values.astype(float).reshape(-1, 1)
    
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(values)
    
    X, y = make_sequences(scaled.flatten(), seq_len)
    X = torch.FloatTensor(X).unsqueeze(-1)
    y = torch.FloatTensor(y).unsqueeze(-1)
    
    model = LSTMModel(input_size=1, hidden_size=64, num_layers=2)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()
    
    model.train()
    loss_history = []
    for epoch in range(epochs):
        optimizer.zero_grad()
        pred = model(X)
        loss = criterion(pred, y)
        loss.backward()
        optimizer.step()
        loss_history.append(loss.item())
    
    # Evaluate on last 60 days
    model.eval()
    with torch.no_grad():
        train_preds = model(X).squeeze().numpy()
    
    fitted_unscaled = scaler.inverse_transform(train_preds.reshape(-1, 1)).flatten()
    actual = values[seq_len:].flatten()
    
    mae = mean_absolute_error(actual[-60:], fitted_unscaled[-60:])
    rmse = np.sqrt(mean_squared_error(actual[-60:], fitted_unscaled[-60:]))
    mape = np.mean(np.abs((actual[-60:] - fitted_unscaled[-60:]) / (actual[-60:] + 1e-6))) * 100
    
    # Multi-step forecast
    forecast = []
    last_seq = scaled[-seq_len:].flatten().tolist()
    
    model.eval()
    with torch.no_grad():
        for _ in range(forecast_days):
            inp = torch.FloatTensor(last_seq[-seq_len:]).unsqueeze(0).unsqueeze(-1)
            pred = model(inp).item()
            forecast.append(pred)
            last_seq.append(pred)
    
    forecast_arr = scaler.inverse_transform(np.array(forecast).reshape(-1, 1)).flatten()
    forecast_arr = np.maximum(forecast_arr, 0)
    
    # Simple confidence band
    std = np.std(values[-90:]) * 0.3
    lower = np.maximum(forecast_arr - std, 0)
    upper = forecast_arr + std
    
    last_date = df["ds"].iloc[-1]
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=forecast_days)
    
    return {
        "model": "LSTM",
        "forecast": forecast_arr.tolist(),
        "lower": lower.tolist(),
        "upper": upper.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(float(mape), 2),
        "loss_history": loss_history,
    }
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Indian festivals and local events that affect demand
INDIAN_EVENTS = {
    # month, day -> (event_name, demand_multiplier)
    (1, 14): ("Makar Sankranti", 1.8),
    (1, 26): ("Republic Day", 1.3),
    (2, 14): ("Valentine's Day", 1.6),
    (3, 25): ("Holi", 2.1),
    (4, 14): ("Baisakhi", 1.5),
    (8, 15): ("Independence Day", 1.4),
    (8, 26): ("Janmashtami", 1.7),
    (10, 2):  ("Gandhi Jayanti", 1.2),
    (10, 20): ("Dussehra", 2.3),
    (11, 1):  ("Diwali -4", 1.9),
    (11, 5):  ("Diwali", 3.2),
    (11, 6):  ("Diwali +1", 2.5),
    (12, 25): ("Christmas", 1.6),
    (12, 31): ("New Year's Eve", 2.0),
}

PRODUCTS = {
    "Atta (5kg)":        {"base": 45, "seasonality": "mild",   "category": "Grocery"},
    "Basmati Rice (2kg)":{"base": 38, "seasonality": "festival","category": "Grocery"},
    "Mustard Oil (1L)":  {"base": 22, "seasonality": "winter", "category": "Grocery"},
    "Soap (Lifebuoy)":   {"base": 60, "seasonality": "summer", "category": "FMCG"},
    "Biscuits (Parle-G)":{"base": 90, "seasonality": "mild",   "category": "FMCG"},
    "Chai Patti (250g)": {"base": 55, "seasonality": "winter", "category": "Grocery"},
    "Dettol Sanitizer":  {"base": 30, "seasonality": "summer", "category": "Health"},
    "Notebook (A4)":     {"base": 40, "seasonality": "school", "category": "Stationery"},
    "Pen (Blue, 10pk)":  {"base": 35, "seasonality": "school", "category": "Stationery"},
    "Agarbatti (Pack)":  {"base": 25, "seasonality": "festival","category": "Pooja"},
}

def get_event_multiplier(date):
    key = (date.month, date.day)
    if key in INDIAN_EVENTS:
        return INDIAN_EVENTS[key][1], INDIAN_EVENTS[key][0]
    # Check nearby festival window (±3 days of Diwali)
    for (m, d), (name, mult) in INDIAN_EVENTS.items():
        event_date = datetime(date.year, m, d)
        if abs((date - event_date).days) <= 3:
            decay = 1 + (mult - 1) * 0.4
            return decay, f"Near {name}"
    return 1.0, None

def get_seasonality_factor(date, season_type):
    month = date.month
    if season_type == "winter":
        # Peak Nov-Feb
        factors = {11:1.4, 12:1.6, 1:1.5, 2:1.3}
        return factors.get(month, 0.85)
    elif season_type == "summer":
        factors = {4:1.2, 5:1.5, 6:1.6, 7:1.3, 8:1.2}
        return factors.get(month, 0.9)
    elif season_type == "festival":
        factors = {10:1.5, 11:1.8, 12:1.3, 1:1.2, 8:1.3}
        return factors.get(month, 0.95)
    elif season_type == "school":
        factors = {6:1.8, 7:1.6, 1:1.5}
        return factors.get(month, 0.7)
    return 1.0

def generate_sales_data(product_name, days=730):
    product = PRODUCTS[product_name]
    base_demand = product["base"]
    season_type = product["seasonality"]
    
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(days)]
    sales = []
    events_log = []
    
    for date in dates:
        # Weekly pattern (Sunday peak in Indian markets)
        weekday_factor = [0.85, 0.90, 0.95, 1.0, 1.05, 1.15, 1.30][date.weekday()]
        
        # Monthly pattern (salary cycles — peak around 1st-5th)
        day_of_month = date.day
        monthly_factor = 1.25 if day_of_month <= 5 else (1.1 if day_of_month <= 10 else 1.0)
        
        # Seasonality
        season_factor = get_seasonality_factor(date, season_type)
        
        # Events
        event_factor, event_name = get_event_multiplier(date)
        if event_name:
            events_log.append({"date": date.strftime("%Y-%m-%d"), "event": event_name, "boost": round(event_factor, 2)})
        
        # Trend (slight upward growth)
        day_idx = (date - datetime(2023, 1, 1)).days
        trend = 1 + (day_idx / days) * 0.15
        
        # Noise
        noise = np.random.normal(1.0, 0.08)
        
        demand = base_demand * weekday_factor * monthly_factor * season_factor * event_factor * trend * noise
        sales.append(max(0, round(demand)))
    
    df = pd.DataFrame({"ds": dates, "y": sales})
    return df, events_log

def get_all_products():
    return list(PRODUCTS.keys())

def get_product_info(product_name):
    return PRODUCTS.get(product_name, {})
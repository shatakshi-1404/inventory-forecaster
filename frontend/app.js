// ─── State ─────────────────────────────────────────────────────────────────
const API = "";  // empty — uses same origin, no CORS
let state = {
  products: [],
  selectedProduct: null,
  model: "all",
  forecastDays: 30,
  historyDays: 120,
  loading: false,
  data: null,
  error: null,
  activeTab: "all",
};

// ─── Chart instances ────────────────────────────────────────────────────────
let historyChart = null;
let forecastChart = null;

// ─── Bootstrap ──────────────────────────────────────────────────────────────
async function init() {
  try {
    const res = await fetch(`${API}/api/products`);
        const json = await res.json();
    state.products = json.products;
    renderProductList();
  } catch (e) {
    document.getElementById("product-list").innerHTML =
      `<div class="error-state">⚠️ Cannot reach backend at ${API}. Is the server running?</div>`;
  }
}

// ─── Render sidebar product list ─────────────────────────────────────────────
function renderProductList() {
  const container = document.getElementById("product-list");
  const icons = ["🌾","🍚","🫙","🧼","🍪","🍵","🧴","📓","🖊️","🪔"];
  container.innerHTML = state.products.map((p, i) => `
    <button class="product-btn ${state.selectedProduct === p ? "active" : ""}"
            onclick="selectProduct('${p}')">
      <span>${icons[i] || "📦"}</span>
      <span>${p}</span>
    </button>
  `).join("");
}

function selectProduct(p) {
  state.selectedProduct = p;
  state.data = null;
  state.error = null;
  renderProductList();
  renderContent();
}

// ─── Forecast trigger ────────────────────────────────────────────────────────
async function runForecast() {
  if (!state.selectedProduct) return;
  state.loading = true;
  state.error = null;
  renderContent();

  try {
    const res = await fetch(`${API}/api/forecast`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product: state.selectedProduct,
        model: state.model,
        forecast_days: state.forecastDays,
        history_days: state.historyDays,
      }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || "Server error");
    state.data = json;
  } catch (e) {
    state.error = e.message;
  } finally {
    state.loading = false;
    renderContent();
  }
}

// ─── Main render ─────────────────────────────────────────────────────────────
function renderContent() {
  const content = document.getElementById("content");

  if (!state.selectedProduct) {
    content.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📦</div>
        <div class="empty-title">Select a product to begin</div>
        <p>Choose from the sidebar to generate demand forecasts</p>
      </div>`;
    return;
  }

  if (state.loading) {
    content.innerHTML = `
      <div class="empty-state">
        <div class="spinner" style="margin:0 auto 16px"></div>
        <div class="empty-title">Running models…</div>
        <p>ARIMA · Prophet · LSTM — computing forecasts</p>
      </div>`;
    return;
  }

  if (state.error) {
    content.innerHTML = `<div class="error-state">⚠️ ${state.error}</div>`;
    return;
  }

  if (!state.data) {
    content.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔮</div>
        <div class="empty-title">${state.selectedProduct}</div>
        <p>Click <strong style="color:var(--green)">Run Forecast</strong> to generate predictions</p>
      </div>`;
    return;
  }

  const { history, stats, forecasts, upcoming_events } = state.data;

  content.innerHTML = `
    ${renderStats(stats)}
    <div class="card">
      <div class="card-header">
        <span class="card-title"><span class="card-icon">📈</span> Sales History + Forecast</span>
        <div class="tabs" id="chart-tabs">
          <button class="tab-btn active" onclick="switchTab('all')">All Models</button>
          ${Object.keys(forecasts).filter(m => !forecasts[m].error).map(m => `
            <button class="tab-btn" onclick="switchTab('${m}')">${m.toUpperCase()}</button>
          `).join("")}
        </div>
      </div>
      <div class="card-body">
        <div class="chart-wrap"><canvas id="forecast-chart"></canvas></div>
      </div>
    </div>
    ${renderModelComparison(forecasts)}
    ${upcoming_events?.length ? renderEvents(upcoming_events) : ""}
    ${renderRecommendation(stats, forecasts)}
  `;

  // Draw chart after DOM update
  setTimeout(() => drawForecastChart(history, forecasts, state.activeTab), 50);
}

// ─── Stats ───────────────────────────────────────────────────────────────────
function renderStats(stats) {
  const trendUp = stats.trend_pct >= 0;
  return `
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">Avg Daily Sales</div>
        <div class="stat-value">${stats.avg_daily}</div>
        <div class="stat-delta ${trendUp ? "delta-up" : "delta-down"}">
          ${trendUp ? "↑" : "↓"} ${Math.abs(stats.trend_pct)}% vs prev month
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Peak (30d)</div>
        <div class="stat-value">${stats.max_daily}</div>
        <div class="stat-delta" style="color:var(--text-muted)">units/day</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Min (30d)</div>
        <div class="stat-value">${stats.min_daily}</div>
        <div class="stat-delta" style="color:var(--text-muted)">units/day</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total (30d)</div>
        <div class="stat-value">${stats.total_30d}</div>
        <div class="stat-delta" style="color:var(--text-muted)">units sold</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Reorder Signal</div>
        <div class="stat-value" style="font-size:16px;color:${trendUp ? "var(--green)" : "var(--yellow)"}">
          ${trendUp ? "📈 Rising" : "📉 Stable"}
        </div>
        <div class="stat-delta" style="color:var(--text-muted)">demand trend</div>
      </div>
    </div>
  `;
}

// ─── Model Comparison ────────────────────────────────────────────────────────
function renderModelComparison(forecasts) {
  const models = ["arima", "prophet", "lstm"];
  const colors = {arima: "arima", prophet: "prophet", lstm: "lstm"};

  const cards = models.map(m => {
    const f = forecasts[m];
    if (!f) return "";
    if (f.error) return `
      <div class="model-card ${colors[m]}">
        <div class="model-name">${m}</div>
        <div class="error-state" style="font-size:11px">Error: ${f.error}</div>
      </div>`;
    const avg = Math.round(f.forecast.reduce((a,b) => a+b,0) / f.forecast.length);
    return `
      <div class="model-card ${colors[m]}">
        <div class="model-name">${m}</div>
        <div class="model-metric">
          <span class="metric-key">MAE</span>
          <span class="metric-val">${f.mae}</span>
        </div>
        <div class="model-metric">
          <span class="metric-key">RMSE</span>
          <span class="metric-val">${f.rmse}</span>
        </div>
        <div class="model-metric">
          <span class="metric-key">MAPE</span>
          <span class="metric-val">${f.mape}%</span>
        </div>
        ${m === "arima" && f.order ? `<div class="model-metric"><span class="metric-key">Order</span><span class="metric-val">${f.order}</span></div>` : ""}
        <div class="model-avg">
          Avg forecast/day
          <span class="avg-val">${avg} units</span>
        </div>
      </div>`;
  });

  return `
    <div class="card">
      <div class="card-header">
        <span class="card-title"><span class="card-icon">🧠</span> Model Comparison</span>
        <span style="font-size:11px;color:var(--text-muted)">Lower MAE/RMSE/MAPE = better</span>
      </div>
      <div class="card-body">
        <div class="model-grid">${cards.join("")}</div>
      </div>
    </div>`;
}

// ─── Events ──────────────────────────────────────────────────────────────────
function renderEvents(events) {
  return `
    <div class="card">
      <div class="card-header">
        <span class="card-title"><span class="card-icon">🎉</span> Upcoming Events in Forecast Window</span>
      </div>
      <div class="card-body" style="padding:0">
        <table class="events-table">
          <thead><tr><th>Date</th><th>Event</th><th>Demand Boost</th></tr></thead>
          <tbody>
            ${events.map(e => `
              <tr>
                <td style="font-family:var(--font-mono);color:var(--text-muted)">${e.date}</td>
                <td>${e.event}</td>
                <td><span class="boost-pill">×${e.boost}</span></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>`;
}

// ─── Recommendation ──────────────────────────────────────────────────────────
function renderRecommendation(stats, forecasts) {
  const forecasted = Object.values(forecasts)
    .filter(f => f.forecast)
    .map(f => f.forecast.reduce((a,b) => a+b,0) / f.forecast.length);
  if (!forecasted.length) return "";

  const avgForecast = Math.round(forecasted.reduce((a,b) => a+b,0) / forecasted.length);
  const safetyStock = Math.round(avgForecast * 7 * 1.25);
  const trendUp = stats.trend_pct >= 0;

  return `
    <div class="rec-box">
      <span class="rec-icon">💡</span>
      <div class="rec-text">
        <strong>Procurement Recommendation</strong><br>
        Based on model consensus, daily demand is projected at <strong>${avgForecast} units/day</strong>.
        ${trendUp ? "Demand is <strong>trending upward</strong> — consider building safety stock." : "Demand appears <strong>stable to declining</strong>."}
        Recommended stock for next 7 days: <strong>${safetyStock} units</strong> (avg forecast × 7 × 1.25 safety buffer).
        ${stats.trend_pct > 15 ? " ⚠️ High growth detected — review supplier lead times." : ""}
      </div>
    </div>`;
}

// ─── Chart ───────────────────────────────────────────────────────────────────
const MODEL_COLORS = {
  arima:   { border: "#58a6ff", bg: "rgba(88,166,255,0.08)", fill: "rgba(88,166,255,0.15)" },
  prophet: { border: "#bc8cff", bg: "rgba(188,140,255,0.08)", fill: "rgba(188,140,255,0.15)" },
  lstm:    { border: "#ffa657", bg: "rgba(255,166,87,0.08)", fill: "rgba(255,166,87,0.15)" },
};

function drawForecastChart(history, forecasts, tab) {
  const canvas = document.getElementById("forecast-chart");
  if (!canvas) return;
  if (forecastChart) { forecastChart.destroy(); forecastChart = null; }

  const ctx = canvas.getContext("2d");

  const histDates = history.dates;
  const histVals  = history.sales;

  // Which models to show
  const modelsToShow = tab === "all"
    ? Object.keys(forecasts).filter(m => forecasts[m] && !forecasts[m].error)
    : [tab].filter(m => forecasts[m] && !forecasts[m].error);

  const forecastDates = modelsToShow.length
    ? forecasts[modelsToShow[0]].dates
    : [];

  const allLabels = [...histDates, ...forecastDates];

  const datasets = [
    {
      label: "Actual Sales",
      data: [...histVals, ...new Array(forecastDates.length).fill(null)],
      borderColor: "#3fb950",
      backgroundColor: "transparent",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      order: 10,
    },
    // Divider line
    {
      label: "Today",
      data: allLabels.map((_, i) => i === histDates.length - 1 ? Math.max(...histVals) * 1.05 : null),
      borderColor: "rgba(255,255,255,0.15)",
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
      tension: 0,
      order: 9,
    },
    ...modelsToShow.map(m => {
      const f = forecasts[m];
      const c = MODEL_COLORS[m];
      return [
        // Confidence band upper
        {
          label: `${m.toUpperCase()} Upper`,
          data: [...new Array(histDates.length).fill(null), ...f.upper],
          borderColor: "transparent",
          backgroundColor: c.fill,
          fill: `+1`,
          pointRadius: 0,
          tension: 0.3,
          order: 2,
        },
        // Confidence band lower
        {
          label: `${m.toUpperCase()} Lower`,
          data: [...new Array(histDates.length).fill(null), ...f.lower],
          borderColor: "transparent",
          backgroundColor: "transparent",
          fill: false,
          pointRadius: 0,
          tension: 0.3,
          order: 2,
        },
        // Forecast line
        {
          label: `${m.toUpperCase()} Forecast`,
          data: [...new Array(histDates.length).fill(null), ...f.forecast],
          borderColor: c.border,
          backgroundColor: "transparent",
          borderWidth: 2,
          borderDash: [6, 3],
          pointRadius: 0,
          tension: 0.3,
          order: 1,
        },
      ];
    }).flat(),
  ];

  forecastChart = new Chart(ctx, {
    type: "line",
    data: { labels: allLabels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: {
            color: "#7d8590",
            font: { family: "Inter", size: 11 },
            usePointStyle: true,
            filter: item => !["Today","ARIMA Upper","ARIMA Lower","PROPHET Upper","PROPHET Lower","LSTM Upper","LSTM Lower"].includes(item.text),
          },
        },
        tooltip: {
          backgroundColor: "#161b22",
          borderColor: "#30363d",
          borderWidth: 1,
          titleColor: "#e6edf3",
          bodyColor: "#7d8590",
          titleFont: { family: "Inter", size: 12 },
          bodyFont: { family: "JetBrains Mono", size: 11 },
          filter: item => item.raw !== null && !item.dataset.label.includes("Upper") && !item.dataset.label.includes("Lower") && item.dataset.label !== "Today",
        },
      },
      scales: {
        x: {
          grid: { color: "#21262d", drawBorder: false },
          ticks: {
            color: "#7d8590",
            font: { family: "JetBrains Mono", size: 10 },
            maxTicksLimit: 10,
            maxRotation: 0,
          },
        },
        y: {
          grid: { color: "#21262d", drawBorder: false },
          ticks: {
            color: "#7d8590",
            font: { family: "JetBrains Mono", size: 10 },
          },
          beginAtZero: false,
        },
      },
    },
  });
}

// ─── Tab switch ──────────────────────────────────────────────────────────────
function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach(b => {
    b.classList.toggle("active", b.textContent.toLowerCase() === tab || (tab === "all" && b.textContent === "All Models"));
  });
  if (state.data) {
    drawForecastChart(state.data.history, state.data.forecasts, tab);
  }
}

// ─── Controls ────────────────────────────────────────────────────────────────
function onModelChange(val) {
  state.model = val;
}

function onForecastDaysChange(val) {
  state.forecastDays = parseInt(val);
  document.getElementById("forecast-days-val").textContent = `${val}d`;
}

function onHistoryDaysChange(val) {
  state.historyDays = parseInt(val);
  document.getElementById("history-days-val").textContent = `${val}d`;
}

// ─── Start ───────────────────────────────────────────────────────────────────
init();
const state = {
  data: null,
  datasetKey: "all",
  date: "",
  search: "",
};

const GROUP_COLORS = {
  "化工品": "#0969da",
  "贵金属": "#bf8700",
  "有色": "#2da44e",
  "农产品": "#cf222e",
};

const REQUIRED_FUTURES_GROUPS = ["化工品", "农产品", "有色", "贵金属"];
const MA_WINDOWS = [5, 10, 60, 250];

const MATRIX_COLUMNS = [
  ["flag", "标注"],
  ["asset_code", "代码"],
  ["asset_name_cn", "中文名"],
  ["asset_name", "英文名"],
  ["day_trend", "日K"],
  ["day_trend_duration", "日K bar"],
  ["week_trend", "周K"],
  ["week_trend_duration", "周K bar"],
  ["month_trend", "月K"],
  ["month_trend_duration", "月K bar"],
  ["relative_state", "比价状态"],
  ["relative_state_duration", "比价bar"],
  ["relative_state_return", "比价状态涨幅"],
  ["capital_state", "资金状态"],
  ["capital_state_duration", "资金bar"],
  ["capital_daily_change", "资金日变化"],
  ["capital_value", "资金值"],
];

const SEARCH_COLUMNS = [
  ["asset_code", "代码"],
  ["asset_name_cn", "中文名"],
  ["asset_name", "英文名"],
  ["dataset_date", "日期"],
  ["dataset_type", "数据集"],
  ["decision", "判断多空"],
  ["day_trend", "日K"],
  ["day_trend_duration", "日K bar"],
  ["week_trend", "周K"],
  ["week_trend_duration", "周K bar"],
  ["month_trend", "月K"],
  ["month_trend_duration", "月K bar"],
  ["relative_state", "比价"],
  ["relative_state_duration", "比价bar"],
  ["relative_state_return", "比价状态涨幅"],
  ["capital_state", "资金"],
  ["capital_state_duration", "资金bar"],
  ["capital_daily_change", "资金日变化"],
  ["capital_value", "资金值"],
  ["relative_strength", "相对强度"],
  ["strength_momentum", "强度动量"],
];

async function main() {
  const response = await fetch("./data/app-data.json", { cache: "no-store" });
  state.data = await response.json();
  initControls();
  render();
}

function initControls() {
  const datasetSelect = document.querySelector("#datasetSelect");
  datasetSelect.innerHTML = [
    `<option value="all">全部</option>`,
    ...state.data.datasetTypes.map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`),
  ].join("");
  datasetSelect.addEventListener("change", () => {
    state.datasetKey = datasetSelect.value;
    const dates = datesForCurrentDataset();
    state.date = dates.at(-1) || "";
    syncDateSelect();
    render();
  });

  const dates = datesForCurrentDataset();
  state.date = dates.at(-1) || "";
  syncDateSelect();

  document.querySelector("#assetSearch").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderSearch();
  });
}

function syncDateSelect() {
  const dateSelect = document.querySelector("#dateSelect");
  const dates = datesForCurrentDataset();
  dateSelect.innerHTML = dates.map((date) => `<option value="${date}">${date}</option>`).join("");
  dateSelect.value = state.date;
  dateSelect.onchange = () => {
    state.date = dateSelect.value;
    render();
  };
}

function datesForCurrentDataset() {
  return state.data.datesByType[state.datasetKey] || [];
}

function currentSnapshot() {
  return state.data.snapshots[`${state.datasetKey}|${state.date}`];
}

function render() {
  const snapshot = currentSnapshot();
  document.querySelector("#generatedAt").textContent = `数据生成：${state.data.generatedAt}；当前日期：${state.date || "-"}`;
  if (!snapshot) return;

  const rows = snapshot.latestRows || [];
  const longRows = filterLong(rows);
  const shortRows = filterShort(rows);

  renderMetrics(snapshot, longRows, shortRows);
  document.querySelector("#longMatrix").innerHTML = tableHtml(sortPreview(longRows), MATRIX_COLUMNS);
  document.querySelector("#shortMatrix").innerHTML = tableHtml(sortPreview(shortRows), MATRIX_COLUMNS);
  renderKlinePanel("#longKlinePanel", sortPreview(longRows));
  renderKlinePanel("#shortKlinePanel", sortPreview(shortRows));
  renderRelativeCrossSection(rows);
  renderMonthlyTrajectories();
  renderTrendBars();
  renderSearch();
}

function renderMetrics(snapshot, longRows, shortRows) {
  const counts = snapshot.latestCounts || {};
  const items = [
    ["日期", snapshot.latestDate || "-"],
    ["全部标的", counts.total || 0],
    ["做多筛选", longRows.length],
    ["做空筛选", shortRows.length],
    ["数据集", state.datasetKey === "all" ? "全部" : state.datasetKey],
  ];
  document.querySelector("#metrics").innerHTML = items
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function filterLong(rows) {
  return rows.filter((row) => {
    const stateName = text(row.relative_state).toLowerCase();
    return (
      ["improving", "lead"].includes(stateName) &&
      text(row.capital_state) === "加杠杆" &&
      isUp(row.week_trend) &&
      isUp(row.day_trend)
    );
  });
}

function filterShort(rows) {
  return rows.filter((row) => {
    const stateName = text(row.relative_state).toLowerCase();
    return (
      ["weakening", "lag"].includes(stateName) &&
      text(row.capital_state) === "去杠杆" &&
      isDown(row.week_trend) &&
      isDown(row.day_trend)
    );
  });
}

function sortPreview(rows) {
  return [...rows].sort(
    (a, b) =>
      number(a.relative_state_duration) - number(b.relative_state_duration) ||
      number(a.capital_state_duration) - number(b.capital_state_duration) ||
      number(a.day_trend_duration) - number(b.day_trend_duration) ||
      text(a.asset_code).localeCompare(text(b.asset_code))
  );
}

function renderKlinePanel(selector, rows) {
  const container = document.querySelector(selector);
  if (!rows.length) {
    container.innerHTML = `<div class="empty">当前日期无符合条件标的。</div>`;
    return;
  }
  const withPrice = rows.filter((row) => priceHistory(row).length);
  const missing = rows.filter((row) => !priceHistory(row).length);
  container.innerHTML = `
    <div class="kline-summary">有行情：${withPrice.length} 个；缺行情：${missing.length} 个。</div>
    ${missing.length ? `<details class="missing" open><summary>缺行情标的</summary>${missing.map((row) => `<span class="pill">${displayName(row)} <code>${escapeHtml(row.asset_code)}</code></span>`).join("")}</details>` : ""}
    <div class="kline-grid">
      ${withPrice
        .slice(0, 24)
        .map(
          (row, index) => `
          <article class="kline-card">
            <h3>${displayName(row)} <code>${escapeHtml(row.asset_code)}</code></h3>
            <div class="kline-chart" id="${chartDomId(selector, row, index, "daily")}"></div>
            <div class="kline-chart" id="${chartDomId(selector, row, index, "weekly")}"></div>
          </article>`
        )
        .join("")}
    </div>
    ${withPrice.length > 24 ? `<p class="hint">为控制页面性能，当前只展示前 24 个有行情候选的 K 线图。</p>` : ""}
  `;
  requestAnimationFrame(() => {
    withPrice.slice(0, 24).forEach((row, index) => {
      const daily = priceHistory(row);
      drawKline(chartDomId(selector, row, index, "daily"), daily, `${displayName(row)} 日K`);
      drawKline(chartDomId(selector, row, index, "weekly"), toWeeklyBars(daily), `${displayName(row)} 周K`);
    });
  });
}

function renderRelativeCrossSection(rows) {
  const plotRows = rows.filter((row) => isFinite(number(row.relative_state_duration)) && isFinite(number(row.relative_state_return)));
  const groups = groupBy(plotRows, (row) => text(row.relative_state) || "未知");
  const traces = Object.entries(groups).map(([name, items]) => ({
    name,
    type: "scatter",
    mode: "markers",
    x: items.map((row) => number(row.relative_state_duration)),
    y: items.map((row) => number(row.relative_state_return)),
    text: items.map((row) => `${displayName(row)} ${row.asset_code}`),
    marker: { size: 8 },
    hovertemplate: "标的=%{text}<br>持续时间=%{x}<br>涨幅=%{y:.2f}<extra></extra>",
  }));
  Plotly.newPlot(
    "relativeCrossSection",
    traces,
    {
      height: 460,
      margin: { l: 56, r: 24, t: 20, b: 52 },
      xaxis: { title: "当前比价状态持续时间" },
      yaxis: { title: "当前比价状态涨幅" },
      legend: { orientation: "h" },
    },
    { displayModeBar: false, responsive: true }
  );
}

function renderMonthlyTrajectories() {
  const latestCoreDate = (state.data.datesByType.core || []).at(-1);
  const source = state.data.futuresByDate[latestCoreDate] || [];
  const cutoff = monthCutoff(latestCoreDate);
  const filtered = source
    .filter((item) => REQUIRED_FUTURES_GROUPS.includes(item.group))
    .map((item) => ({ ...item, points: item.points.filter((point) => point.date >= cutoff) }))
    .filter((item) => item.points.length);
  const groups = groupBy(filtered, (item) => item.group);

  document.querySelector("#monthlyTrajectories").innerHTML = REQUIRED_FUTURES_GROUPS
    .map((group) => `<h3 class="group-title">${group}</h3><div class="wide-chart" id="monthly-${slug(group)}"></div>`)
    .join("");

  for (const group of REQUIRED_FUTURES_GROUPS) {
    const items = groups[group] || [];
    drawQuadrantBundle(`monthly-${slug(group)}`, items, `${group} 一个月轨迹线`);
  }
}

function renderTrendBars() {
  const latestCoreDate = (state.data.datesByType.core || []).at(-1);
  const dates = (state.data.datesByType.core || []).filter((date) => date >= monthCutoff(latestCoreDate));
  const latestFutures = state.data.futuresByDate[latestCoreDate] || [];
  const byCode = new Map(latestFutures.map((item) => [item.assetCode, item.group]));
  document.querySelector("#trendBars").innerHTML = REQUIRED_FUTURES_GROUPS
    .map((group) => `<h3 class="group-title">${group}</h3><div class="wide-chart" id="trend-${slug(group)}"></div>`)
    .join("");

  for (const group of REQUIRED_FUTURES_GROUPS) {
    const traces = ["day", "week", "month"].map((period) => {
      const values = dates.map((date) => {
        const snapshot = state.data.snapshots[`core|${date}`];
        const rows = (snapshot?.latestRows || []).filter((row) => byCode.get(row.asset_code) === group);
        return sumTrendBars(rows, period);
      });
      return { type: "bar", name: periodLabel(period), x: dates, y: values };
    });
    Plotly.newPlot(
      `trend-${slug(group)}`,
      traces,
      {
        barmode: "group",
        height: 360,
        margin: { l: 56, r: 24, t: 20, b: 52 },
        xaxis: { title: "一个月日期" },
        yaxis: { title: "bar数：上行正 / 下行负 / 无趋势0" },
      },
      { displayModeBar: false, responsive: true }
    );
  }
}

function renderSearch() {
  const snapshot = currentSnapshot();
  if (!snapshot) return;
  const query = state.search;
  const rows = (snapshot.latestRows || [])
    .filter((row) => !query || [row.asset_code, row.asset_name_cn, row.asset_name, row.asset_key].filter(Boolean).join(" ").toLowerCase().includes(query))
    .slice(0, 200)
    .map((row) => ({ ...row, decision: decisionLabel(row) }));
  document.querySelector("#searchPanel").innerHTML = query
    ? tableHtml(rows, SEARCH_COLUMNS)
    : `<div class="empty">输入关键字后显示相关标的面板数据。</div>`;
}

function tableHtml(rows, cols) {
  if (!rows.length) return `<div class="empty">暂无数据</div>`;
  const head = cols.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("");
  const body = rows
    .map((row) => `<tr class="${hasAnyBarOne(row) ? "bar-one" : ""}">${cols.map(([key]) => `<td>${formatCell(key, row)}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function formatCell(key, row) {
  if (key === "flag") return hasAnyBarOne(row) ? `<span class="tag hot">bar=1</span>` : "";
  const value = row[key];
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (key === "decision") return `<span class="tag ${decisionClass(value)}">${escapeHtml(value)}</span>`;
  if (key.endsWith("_duration") && number(value) === 1) return `<span class="tag hot">1</span>`;
  return escapeHtml(String(value));
}

function drawQuadrantBundle(elementId, items, title) {
  const values = items.flatMap((item) => item.points.flatMap((point) => [Math.abs(point.x), Math.abs(point.y)])).filter(Number.isFinite);
  const axis = Math.max(10, Math.max(...values, 0) * 1.2);
  const traces = items.map((item) => ({
    type: "scatter",
    mode: "lines+markers",
    name: item.displayName,
    x: item.points.map((point) => point.x),
    y: item.points.map((point) => point.y),
    text: item.points.map((point) => `${item.displayName} ${point.date}`),
    line: { width: 1.5, color: GROUP_COLORS[item.group] || "#8c959f" },
    marker: { size: 5 },
    hovertemplate: "%{text}<br>相对强度-100=%{x:.2f}<br>强度动量-100=%{y:.2f}<extra></extra>",
  }));
  Plotly.newPlot(
    elementId,
    traces,
    {
      title,
      height: 430,
      margin: { l: 48, r: 20, t: 44, b: 44 },
      xaxis: { title: "相对强度 - 100", range: [-axis, axis], zeroline: false },
      yaxis: { title: "强度动量 - 100", range: [-axis, axis], zeroline: false, scaleanchor: "x", scaleratio: 1 },
      shapes: quadrantShapes(axis),
      showlegend: false,
    },
    { displayModeBar: false, responsive: true }
  );
}

function drawKline(elementId, bars, title) {
  const cleanBars = bars.filter((bar) => bar.open !== null && bar.high !== null && bar.low !== null && bar.close !== null);
  const x = cleanBars.map((bar) => bar.bar_date);
  const traces = [
    {
      type: "candlestick",
      name: "K线",
      x,
      open: cleanBars.map((bar) => bar.open),
      high: cleanBars.map((bar) => bar.high),
      low: cleanBars.map((bar) => bar.low),
      close: cleanBars.map((bar) => bar.close),
      increasing: { line: { color: "#cf222e" } },
      decreasing: { line: { color: "#1a7f37" } },
    },
    ...MA_WINDOWS.map((window) => ({
      type: "scatter",
      mode: "lines",
      name: `MA${window}`,
      x,
      y: movingAverage(cleanBars.map((bar) => bar.close), window),
      line: { width: 1.4 },
    })),
  ];
  Plotly.newPlot(
    elementId,
    traces,
    {
      title,
      height: 320,
      margin: { l: 48, r: 16, t: 36, b: 32 },
      xaxis: { rangeslider: { visible: false } },
      yaxis: { title: "价格" },
      legend: { orientation: "h", y: -0.15 },
    },
    { displayModeBar: false, responsive: true }
  );
}

function movingAverage(values, window) {
  return values.map((_, index) => {
    if (index + 1 < window) return null;
    const slice = values.slice(index + 1 - window, index + 1).filter((value) => value !== null && value !== undefined);
    if (slice.length < window) return null;
    return slice.reduce((sum, value) => sum + Number(value), 0) / window;
  });
}

function toWeeklyBars(dailyBars) {
  const groups = new Map();
  for (const bar of dailyBars) {
    const key = weekKey(bar.bar_date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(bar);
  }
  return [...groups.values()].map((items) => {
    const sorted = [...items].sort((a, b) => a.bar_date.localeCompare(b.bar_date));
    return {
      bar_date: sorted.at(-1).bar_date,
      open: sorted[0].open,
      high: Math.max(...sorted.map((bar) => number(bar.high))),
      low: Math.min(...sorted.map((bar) => number(bar.low))),
      close: sorted.at(-1).close,
      volume: sorted.reduce((sum, bar) => sum + number(bar.volume), 0),
    };
  });
}

function weekKey(dateText) {
  const date = new Date(`${dateText}T00:00:00`);
  const day = date.getDay() || 7;
  date.setDate(date.getDate() + 4 - day);
  const yearStart = new Date(date.getFullYear(), 0, 1);
  const week = Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
  return `${date.getFullYear()}-${String(week).padStart(2, "0")}`;
}

function priceHistory(row) {
  const histories = state.data.priceHistories || {};
  return histories[row.asset_key] || histories[`${row.asset_code}|${row.asset_name}`] || histories[row.asset_code] || [];
}

function chartDomId(selector, row, index, suffix) {
  return `${selector.replace(/[^a-zA-Z0-9]/g, "")}-${slug(row.asset_code)}-${index}-${suffix}`;
}

function quadrantShapes(axis) {
  return [
    [0, 0, axis, axis, "rgba(46,160,67,0.08)"],
    [-axis, 0, 0, axis, "rgba(9,105,218,0.08)"],
    [-axis, -axis, 0, 0, "rgba(207,34,46,0.07)"],
    [0, -axis, axis, 0, "rgba(191,135,0,0.08)"],
  ].map(([x0, y0, x1, y1, fillcolor]) => ({ type: "rect", x0, y0, x1, y1, fillcolor, line: { width: 0 }, layer: "below" }))
    .concat([
      { type: "line", x0: -axis, x1: axis, y0: 0, y1: 0, line: { color: "#9a6700", dash: "dash", width: 1 } },
      { type: "line", x0: 0, x1: 0, y0: -axis, y1: axis, line: { color: "#9a6700", dash: "dash", width: 1 } },
    ]);
}

function sumTrendBars(rows, period) {
  return rows.reduce((total, row) => {
    const trend = row[`${period}_trend`];
    const duration = number(row[`${period}_trend_duration`]);
    if (isUp(trend)) return total + duration;
    if (isDown(trend)) return total - duration;
    return total;
  }, 0);
}

function periodLabel(period) {
  return { day: "日K", week: "周K", month: "月K" }[period] || period;
}

function monthCutoff(dateText) {
  const [year, month, day] = String(dateText).split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setMonth(date.getMonth() - 1);
  return formatDate(date);
}

function formatDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function hasAnyBarOne(row) {
  return ["relative_state_duration", "capital_state_duration", "day_trend_duration", "week_trend_duration", "month_trend_duration"].some((key) => number(row[key]) === 1);
}

function decisionLabel(row) {
  if (isLongRule(row)) return "可做多";
  if (isShortRule(row)) return "可做空";
  return "观望";
}

function isLongRule(row) {
  const stateName = text(row.relative_state).toLowerCase();
  return ["improving", "lead"].includes(stateName) && text(row.capital_state) === "加杠杆" && isUp(row.week_trend) && isUp(row.day_trend);
}

function isShortRule(row) {
  const stateName = text(row.relative_state).toLowerCase();
  return ["weakening", "lag"].includes(stateName) && text(row.capital_state) === "去杠杆" && isDown(row.week_trend) && isDown(row.day_trend);
}

function decisionClass(value) {
  if (String(value).includes("多")) return "long";
  if (String(value).includes("空")) return "short";
  return "";
}

function displayName(row) {
  return text(row.asset_name_cn) || text(row.asset_name) || text(row.asset_code);
}

function groupBy(items, getKey) {
  return items.reduce((groups, item) => {
    const key = getKey(item);
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
    return groups;
  }, {});
}

function isUp(value) {
  return ["上行趋势", "上涨趋势"].includes(text(value));
}

function isDown(value) {
  return ["下行趋势", "下跌趋势"].includes(text(value));
}

function isFlat(value) {
  return ["无趋势", "平", "震荡", ""].includes(text(value));
}

function number(value) {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function text(value) {
  return value === null || value === undefined ? "" : String(value).trim();
}

function slug(value) {
  return String(value || "asset").replace(/[^0-9a-zA-Z\u4e00-\u9fa5_-]/g, "");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

main().catch((error) => {
  document.body.innerHTML = `<main><section><h2>加载失败</h2><pre>${escapeHtml(error.stack || error.message || error)}</pre></section></main>`;
});

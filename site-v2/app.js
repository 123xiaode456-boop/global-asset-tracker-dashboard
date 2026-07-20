const DATA_URL = "./data/app-data.json";

const state = {
  data: null,
  datasetKey: "core",
  date: "",
  activeView: "overview",
  quadrantGroup: "化工品",
  trendGroup: "化工品",
  search: "",
  earlySearch: "",
  momentumSearch: "",
  momentumState: "all",
};

const GROUP_COLORS = {
  "化工品": "#0969da",
  "贵金属": "#bf8700",
  "有色": "#2da44e",
  "农产品": "#cf222e",
  "黑色建材": "#8250df",
  "能源运输": "#bc4c00",
};

const REQUIRED_FUTURES_GROUPS = ["化工品", "农产品", "有色", "贵金属", "黑色建材", "能源运输"];
const VIEW_KEYS = ["overview", "long", "short", "early", "trajectory", "trend", "momentum", "search"];
const MA_WINDOWS = [5, 10, 20, 60, 250];
const RELATIVE_STATE_QUADRANTS = {
  improving: { label: "Improving", xSign: -1, ySign: 1 },
  lead: { label: "Leading", xSign: 1, ySign: 1 },
  leading: { label: "Leading", xSign: 1, ySign: 1 },
  lag: { label: "Lagging", xSign: -1, ySign: -1 },
  lagging: { label: "Lagging", xSign: -1, ySign: -1 },
  weakening: { label: "Weakening", xSign: 1, ySign: -1 },
};
const RETURN_DIRECTIONS = {
  up: { name: "上涨", color: "#cf222e" },
  down: { name: "下跌", color: "#1a7f37" },
};

const MATRIX_COLUMNS = [
  ["flag", "标注"],
  ["asset_code", "代码"],
  ["asset_name_cn", "中文名"],
  ["asset_name", "英文名"],
  ["relative_state_duration", "比价持续"],
  ["relative_state", "比价状态"],
  ["relative_state_return", "比价状态涨幅"],
  ["day_trend", "日K"],
  ["day_trend_duration", "日K bar"],
  ["week_trend", "周K"],
  ["week_trend_duration", "周K bar"],
  ["month_trend", "月K"],
  ["month_trend_duration", "月K bar"],
  ["capital_state_duration", "资金bar"],
  ["capital_state", "资金状态"],
];

const SEARCH_COLUMNS = [
  ["asset_code", "代码"],
  ["asset_name_cn", "中文名"],
  ["asset_name", "英文名"],
  ["decision", "判断多空"],
  ["relative_state_duration", "比价bar"],
  ["relative_state", "比价"],
  ["relative_state_return", "比价状态涨幅"],
  ["day_trend", "日K"],
  ["day_trend_duration", "日K bar"],
  ["week_trend", "周K"],
  ["week_trend_duration", "周K bar"],
  ["month_trend", "月K"],
  ["month_trend_duration", "月K bar"],
  ["capital_state_duration", "资金bar"],
  ["capital_state", "资金"],
];

const MOMENTUM_COLUMNS = [
  ["asset_code", "代码"],
  ["asset_name_cn", "中文名"],
  ["asset_name", "英文名"],
  ["current_momentum_state_duration", "当前状态 bar"],
  ["current_momentum_state", "当前动能状态"],
  ["current_momentum_state_return", "当前状态累积涨跌幅"],
  ["previous_momentum_state", "此前动能状态"],
  ["previous_momentum_state_return", "此前状态累积涨跌幅"],
  ["momentum_value", "动能数值"],
  ["momentum_daily_change", "相比前日变动"],
  ["momentum_change_label", "动能变化解读"],
];

async function main() {
  const response = await fetch(currentDataUrl(), { cache: "no-store" });
  state.data = await response.json();
  initControls();
  render();
  selectView(state.activeView);
}

function currentDataUrl() {
  return `${DATA_URL}?v=${Date.now()}`;
}

function initControls() {
  const datasetSelect = document.querySelector("#datasetSelect");
  datasetSelect.innerHTML = `<option value="core">核心数据集</option>`;
  datasetSelect.value = "core";
  datasetSelect.addEventListener("change", () => {
    state.datasetKey = "core";
    const dates = datesForCurrentDataset();
    state.date = dates.at(-1) || "";
    syncDateSelect();
    render();
    selectView(state.activeView);
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
    selectView(state.activeView);
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

  const allRows = snapshot.latestRows || [];
  const rows = currentCommodityRows(allRows);
  const longRows = filterLong(allRows);
  const shortRows = filterShort(allRows);

  renderMetrics(snapshot, longRows, shortRows);
  renderBarAlerts(rows);
  document.querySelector("#longMatrix").innerHTML = tableHtml(sortPreview(longRows), MATRIX_COLUMNS);
  document.querySelector("#shortMatrix").innerHTML = tableHtml(sortPreview(shortRows), MATRIX_COLUMNS);
  renderKlinePanel("#longKlinePanel", sortPreview(longRows));
  renderKlinePanel("#shortKlinePanel", sortPreview(shortRows));
  renderEarlyView(rows);
  renderMonthlyTrajectories();
  renderTrendBars();
  renderMomentum();
  renderSearch();
}

function renderMetrics(snapshot, longRows, shortRows) {
  const commodityTotal = currentCommodityRows(snapshot.latestRows || []).length;
  const items = [
    ["日期", snapshot.latestDate || "-"],
    ["商品标的", commodityTotal],
    ["bar=1提醒", barAlertRows(currentCommodityRows(snapshot.latestRows || [])).length],
    ["做多筛选", longRows.length],
    ["做空筛选", shortRows.length],
  ];
  document.querySelector("#metrics").innerHTML = items
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function currentCommodityRows(rows) {
  const { keys, codes } = commodityAssetIdentifiersForCurrentDate();
  if (!keys.size && !codes.size) return [];
  return rows.filter((row) => {
    const key = text(row.asset_key);
    if (key) return keys.has(key);
    return codes.has(text(row.asset_code));
  });
}

function commodityAssetIdentifiersForCurrentDate() {
  const items = state.data?.futuresByDate?.[state.date] || [];
  const filtered = items.filter((item) => REQUIRED_FUTURES_GROUPS.includes(item.group));
  return {
    keys: new Set(filtered.map((item) => text(item.assetKey)).filter(Boolean)),
    codes: new Set(filtered.map((item) => text(item.assetCode)).filter(Boolean)),
  };
}

function domesticCommodityRows(rows) {
  const { keys, codes } = domesticCommodityAssetIdentifiersForCurrentDate();
  if (!keys.size && !codes.size) return [];
  return rows.filter((row) => {
    const key = text(row.asset_key);
    if (key) return keys.has(key);
    return codes.has(text(row.asset_code));
  });
}

function domesticCommodityAssetIdentifiersForCurrentDate() {
  const items = state.data?.futuresByDate?.[state.date] || [];
  const filtered = items.filter((item) => REQUIRED_FUTURES_GROUPS.includes(item.group) && isDomesticFuturesItem(item));
  return {
    keys: new Set(filtered.map((item) => text(item.assetKey)).filter(Boolean)),
    codes: new Set(filtered.map((item) => text(item.assetCode)).filter(Boolean)),
  };
}

function isDomesticFuturesItem(item) {
  return item.isDomestic === true || text(item.market).toUpperCase() === "CN" || text(item.marketSource).toLowerCase() === "akshare";
}

function renderBarAlerts(rows) {
  const alertRows = barAlertRows(rows).map((row) => ({ ...row, alert_reason: barOneReasons(row).join(" / ") }));
  const columns = [
    ["alert_reason", "触发"],
    ["asset_code", "代码"],
    ["asset_name_cn", "中文名"],
    ["asset_name", "英文名"],
    ["relative_state_duration", "比价bar"],
    ["relative_state", "比价状态"],
    ["relative_state_return", "比价状态涨幅"],
    ["day_trend", "日K"],
    ["day_trend_duration", "日K bar"],
    ["capital_state_duration", "资金bar"],
    ["capital_state", "资金状态"],
  ];
  document.querySelector("#barAlerts").innerHTML = `
    <h2>今日 bar=1 提醒</h2>
    <p class="rule">当天商品标的中，当前比价状态持续时间、日级别趋势持续时间、当前杠杆资金状态持续时间任意一个等于 1 就列入。</p>
    ${tableHtml(alertRows, columns)}
  `;
}

function barAlertRows(rows) {
  return rows.filter((row) => barOneReasons(row).length).sort(
    (a, b) =>
      number(a.relative_state_duration) - number(b.relative_state_duration) ||
      number(a.day_trend_duration) - number(b.day_trend_duration) ||
      number(a.capital_state_duration) - number(b.capital_state_duration) ||
      text(a.asset_code).localeCompare(text(b.asset_code))
  );
}

function barOneReasons(row) {
  const reasons = [];
  if (number(row.relative_state_duration) === 1) reasons.push("比价=1");
  if (number(row.day_trend_duration) === 1) reasons.push("日K=1");
  if (number(row.capital_state_duration) === 1) reasons.push("资金=1");
  return reasons;
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
      text(a.asset_code).localeCompare(text(b.asset_code))
  );
}

function renderKlinePanel(selector, rows) {
  const container = document.querySelector(selector);
  if (!rows.length) {
    container.innerHTML = `<div class="empty">当前日期无符合条件标的。</div>`;
    return;
  }
  const domesticRows = domesticCommodityRows(rows);
  if (!domesticRows.length) {
    container.innerHTML = `<div class="empty">筛选结果中暂无国内商品期货标的。</div>`;
    return;
  }
  const withPrice = domesticRows.filter((row) => priceHistory(row).length);
  const missing = domesticRows.filter((row) => !priceHistory(row).length);
  container.innerHTML = `
    <div class="kline-summary">国内商品期货行情K线：有缓存日K：${withPrice.length} 个；缺缓存日K：${missing.length} 个；每个品种同时尝试加载实时分钟K。</div>
    ${missing.length ? `<details class="missing" open><summary>缺行情标的</summary>${missing.map((row) => `<span class="pill">${displayName(row)} <code>${escapeHtml(row.asset_code)}</code></span>`).join("")}</details>` : ""}
    <div class="kline-grid">
      ${domesticRows
        .map(
          (row, index) => `
          <article class="kline-card">
            <h3>${displayName(row)} <code>${escapeHtml(row.asset_code)}</code></h3>
            <div class="kline-chart" id="${chartDomId(selector, row, index, "daily")}"></div>
            <div class="kline-chart" id="${chartDomId(selector, row, index, "weekly")}"></div>
            <div class="kline-chart" id="${chartDomId(selector, row, index, "live")}"></div>
          </article>`
        )
        .join("")}
    </div>
  `;
  requestAnimationFrame(() => {
    domesticRows.forEach((row, index) => {
      const daily = priceHistory(row);
      const dailyId = chartDomId(selector, row, index, "daily");
      const weeklyId = chartDomId(selector, row, index, "weekly");
      if (daily.length) {
        drawKline(dailyId, daily, `${displayName(row)} 日K`);
        drawKline(weeklyId, toWeeklyBars(daily), `${displayName(row)} 周K`);
      } else {
        setChartMessage(dailyId, "暂无缓存日K");
        setChartMessage(weeklyId, "暂无缓存周K");
      }
      drawLiveMinuteKline(chartDomId(selector, row, index, "live"), row);
    });
  });
}

function renderEarlyView(rows = currentCommodityRows(currentSnapshot()?.latestRows || [])) {
  const filteredRows = filterEarlyRows(rows);
  syncEarlySearchInput();
  renderEarlySearchStatus(rows.length, filteredRows.length);
  renderRelativeCrossSection(filteredRows);
}

function filterEarlyRows(rows) {
  const query = text(state.earlySearch).trim().toLowerCase();
  if (!query) return rows;
  return rows.filter((row) => {
    const fields = [row.asset_code, row.asset_name_cn, row.asset_name, row.asset_key, displayName(row)];
    return fields.some((value) => text(value).toLowerCase().includes(query));
  });
}

function setEarlySearch(value) {
  state.earlySearch = text(value).trim();
  renderEarlyView();
}

function resetEarlySearch() {
  state.earlySearch = "";
  renderEarlyView();
}

function syncEarlySearchInput() {
  const input = document.querySelector("#earlyAssetSearch");
  if (input && input.value !== state.earlySearch) input.value = state.earlySearch;
}

function renderEarlySearchStatus(totalCount, filteredCount) {
  const status = document.querySelector("#earlySearchStatus");
  if (!status) return;
  status.textContent = `${filteredCount} / ${totalCount}`;
}

function renderRelativeCrossSection(rows) {
  const points = rows.map((row) => ({ row, point: relativeStatePoint(row) })).filter((item) => item.point);
  const markerTraces = ["up", "down"].map((direction) => {
    const directionPoints = points.filter((item) => item.point.direction === direction);
    const config = RETURN_DIRECTIONS[direction];
    return {
      name: config.name,
      type: "scatter",
      mode: "markers",
      x: directionPoints.map((item) => item.point.x),
      y: directionPoints.map((item) => item.point.y),
      text: directionPoints.map((item) => displayName(item.row)),
      marker: { size: 8, color: config.color, opacity: 0.82, line: { width: 1, color: "#202020" } },
      customdata: directionPoints.map((item) => [
        item.row.asset_code,
        text(item.row.relative_state),
        item.point.quadrant,
        item.point.duration,
        item.point.returnValue,
        config.name,
      ]),
      hovertemplate:
        "标的=%{text}<br>代码=%{customdata[0]}<br>比价状态=%{customdata[1]}<br>象限=%{customdata[2]}<br>持续时间=%{customdata[3]}<br>涨跌幅=%{customdata[4]:.2f}<br>方向=%{customdata[5]}<extra></extra>",
    };
  });
  const labelTraces = markerTraces.map((trace) => ({
    name: `${trace.name}标的名称`,
    type: "scatter",
    mode: "text",
    x: trace.x,
    y: trace.y,
    text: trace.text,
    textposition: "middle center",
    textfont: { size: 10, color: "rgba(31, 35, 40, 0.38)" },
    cliponaxis: true,
    hoverinfo: "skip",
    showlegend: false,
  }));
  const traces = markerTraces.concat(labelTraces);
  const xAxis = mirroredAxis(points.map((item) => Math.abs(item.point.x)), 1);
  const yAxis = mirroredAxis(points.map((item) => Math.abs(item.point.y)), 1);
  Plotly.newPlot(
    "relativeCrossSection",
    traces,
    {
      autosize: true,
      height: 760,
      margin: { l: 76, r: 10, t: 16, b: 68 },
      xaxis: { title: "当前比价状态持续时间（左右均为正值）", ...xAxis },
      yaxis: { title: "当前比价状态涨跌幅绝对值（上下均为正值）", ...yAxis },
      shapes: quadrantShapesXY(xAxis.outer, yAxis.outer, { fullZeroAxes: true }),
      annotations: quadrantAnnotations(),
      legend: { orientation: "h" },
      dragmode: "pan",
    },
    { displayModeBar: true, displaylogo: false, responsive: true, scrollZoom: true }
  );
}

function renderMonthlyTrajectories() {
  const date = selectedCoreDate();
  const source = state.data.futuresByDate[date] || [];
  const cutoff = monthCutoff(date);
  const filtered = source
    .filter((item) => REQUIRED_FUTURES_GROUPS.includes(item.group))
    .map((item) => ({ ...item, points: item.points.filter((point) => point.date >= cutoff) }))
    .filter((item) => item.points.length);
  const group = selectedQuadrantGroup();
  const items = filtered.filter((item) => item.group === group);

  document.querySelector("#monthlyTrajectories").innerHTML = `
    <div class="quadrant-tabs">
      ${REQUIRED_FUTURES_GROUPS.map(
        (name) =>
          `<button class="quadrant-tab ${name === group ? "active" : ""}" type="button" onclick="selectQuadrantGroup('${escapeHtml(name)}')">${escapeHtml(name)}</button>`
      ).join("")}
    </div>
    <div class="kline-summary">${escapeHtml(group)}：${items.length} 个品种；每个品种单独一张四象限图，轨迹范围为当前日期往前 30 自然日内已有数据。</div>
    ${
      items.length
        ? `<div class="quadrant-grid">
            ${items
              .map(
                (item, index) => `
                  <article class="quadrant-card">
                    <div class="quadrant-chart" id="quadrant-${slug(group)}-${index}"></div>
                  </article>`
              )
              .join("")}
          </div>`
        : `<div class="empty">当前日期下没有 ${escapeHtml(group)} 的四象限轨迹数据。</div>`
    }
  `;

  items.forEach((item, index) => {
    drawQuadrantBundle(`quadrant-${slug(group)}-${index}`, [item], quadrantAssetLabel(item));
  });
}

function renderTrendBars() {
  const date = selectedCoreDate();
  const dates = coreDatesInLast30Days(date);
  const latestFutures = state.data.futuresByDate[date] || [];
  const group = selectedTrendGroup();
  const items = latestFutures.filter((item) => item.group === group);

  document.querySelector("#trendBars").innerHTML = `
    <div class="quadrant-tabs trend-tabs">
      ${REQUIRED_FUTURES_GROUPS.map(
        (name) =>
          `<button class="quadrant-tab ${name === group ? "active" : ""}" type="button" onclick="selectTrendGroup('${escapeHtml(name)}')">${escapeHtml(name)}</button>`
      ).join("")}
    </div>
    <div class="kline-summary">${escapeHtml(group)}：${items.length} 个品种；每个品种单独一张日/周/月趋势 bar 图，横轴为当前日期往前 30 自然日内已有数据。</div>
    ${
      items.length
        ? `<div class="trend-grid">
            ${items
              .map(
                (item, index) => `
                  <article class="trend-card">
                    <h3>${escapeHtml(futuresDisplayName(item))} <code>${escapeHtml(item.assetCode)}</code></h3>
                    <div class="trend-chart" id="trend-${slug(group)}-${index}"></div>
                  </article>`
              )
              .join("")}
          </div>`
        : `<div class="empty">当前日期下没有 ${escapeHtml(group)} 的三级别趋势数据。</div>`
    }
  `;

  items.forEach((item, index) => {
    const traces = ["day", "week", "month"].map((period) => {
      const values = dates.map((date) => {
        const snapshot = state.data.snapshots[`core|${date}`];
        const row = (snapshot?.latestRows || []).find((candidate) => rowMatchesFuturesItem(candidate, item));
        return trendBarValue(row, period);
      });
      return { type: "bar", name: periodLabel(period), x: dates, y: values };
    });
    Plotly.newPlot(
      `trend-${slug(group)}-${index}`,
      traces,
      {
        barmode: "group",
        height: 320,
        margin: { l: 56, r: 24, t: 20, b: 52 },
        xaxis: { title: "一个月日期", tickangle: -30 },
        yaxis: { title: "bar数：上行正 / 下行负 / 无趋势0" },
        legend: { orientation: "h", y: -0.22 },
      },
      { displayModeBar: false, responsive: true }
    );
  });
}

function momentumRowsForCurrentDate() {
  return (state.data?.momentumByDate?.[state.date] || []).map((row) => ({
    ...row,
    momentum_change_label: momentumStrengthLabel(row),
  }));
}

function filterMomentumRows(rows = momentumRowsForCurrentDate()) {
  const query = text(state.momentumSearch).toLowerCase();
  return rows.filter((row) => {
    const stateMatches = state.momentumState === "all" || momentumStateKind(row) === state.momentumState;
    const searchMatches =
      !query ||
      [row.asset_code, row.asset_name_cn, row.asset_name, row.asset_key]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query);
    return stateMatches && searchMatches;
  });
}

function setMomentumSearch(value) {
  state.momentumSearch = text(value);
  renderMomentum();
}

function setMomentumState(value) {
  const normalized = ["all", "positive", "negative", "dot"].includes(value)
    ? value
    : momentumStateKind({ current_momentum_state: value });
  if (!["all", "positive", "negative", "dot"].includes(normalized)) return;
  state.momentumState = normalized;
  renderMomentum();
}

function momentumStrengthLabel(row) {
  const stateKind = momentumStateKind(row);
  const change = number(row.momentum_daily_change);
  if (stateKind === "positive") {
    if (change > 0) return "正动能增强";
    if (change < 0) return "正动能减弱";
    return "正动能不变";
  }
  if (stateKind === "negative") {
    if (change < 0) return "负动能增强";
    if (change > 0) return "负动能减弱";
    return "负动能不变";
  }
  if (stateKind === "dot") return "动能靠近零轴";
  return "";
}

function rankMomentumRows(rows, direction) {
  const filtered = rows.filter((row) => {
    const stateKind = momentumStateKind(row);
    const change = number(row.momentum_daily_change);
    return direction === "positive"
      ? stateKind === "positive" && change > 0
      : stateKind === "negative" && change < 0;
  });
  filtered.sort((a, b) => {
    const changeOrder = direction === "positive"
      ? number(b.momentum_daily_change) - number(a.momentum_daily_change)
      : number(a.momentum_daily_change) - number(b.momentum_daily_change);
    return changeOrder || Math.abs(number(b.momentum_value)) - Math.abs(number(a.momentum_value));
  });
  return filtered.map((row, index) => ({ ...row, momentum_rank: index + 1 }));
}

function renderMomentum() {
  const allRows = momentumRowsForCurrentDate();
  const rows = filterMomentumRows(allRows);
  const input = document.querySelector("#momentumAssetSearch");
  if (input && input.value !== state.momentumSearch) input.value = state.momentumSearch;
  document.querySelectorAll("[data-momentum-state]").forEach((button) => {
    button.classList.toggle("active", button.dataset.momentumState === state.momentumState);
  });

  const counts = {
    positive: allRows.filter((row) => momentumStateKind(row) === "positive").length,
    negative: allRows.filter((row) => momentumStateKind(row) === "negative").length,
    dot: allRows.filter((row) => momentumStateKind(row) === "dot").length,
    fresh: allRows.filter((row) => number(row.current_momentum_state_duration) === 1).length,
  };
  document.querySelector("#momentumMetrics").innerHTML = [
    ["日期", state.date || "-"],
    ["动量标的", allRows.length],
    ["正动能", counts.positive],
    ["负动能", counts.negative],
    ["打点", counts.dot],
    ["新状态 bar=1", counts.fresh],
  ]
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  document.querySelector("#momentumFilterStatus").textContent = `${rows.length} / ${allRows.length}`;
  const rankColumns = [
    ["momentum_rank", "排名"],
    ["asset_code", "代码"],
    ["asset_name_cn", "中文名"],
    ["asset_name", "英文名"],
    ["current_momentum_state_duration", "状态 bar"],
    ["momentum_value", "动能数值"],
    ["momentum_daily_change", "相比前日"],
    ["momentum_change_label", "变化解读"],
  ];
  const positive = rankMomentumRows(rows, "positive").slice(0, 20);
  const negative = rankMomentumRows(rows, "negative").slice(0, 20);
  const fresh = rows
    .filter((row) => number(row.current_momentum_state_duration) === 1)
    .sort((a, b) => Math.abs(number(b.momentum_daily_change)) - Math.abs(number(a.momentum_daily_change)));
  document.querySelector("#momentumPositiveRank").innerHTML = tableHtml(positive, rankColumns);
  document.querySelector("#momentumNegativeRank").innerHTML = tableHtml(negative, rankColumns);
  document.querySelector("#momentumNewStates").innerHTML = tableHtml(fresh, MOMENTUM_COLUMNS);
  document.querySelector("#momentumTable").innerHTML = tableHtml(rows, MOMENTUM_COLUMNS);
  drawMomentumScatter(rows);
}

function drawMomentumScatter(rows) {
  const stateConfig = {
    positive: { color: "#ff5c7a", label: "正动能" },
    negative: { color: "#2ecc71", label: "负动能" },
    dot: { color: "#f2c94c", label: "打点" },
  };
  const traces = Object.entries(stateConfig).map(([stateKind, config]) => {
    const items = rows.filter((row) => momentumStateKind(row) === stateKind);
    return {
      type: "scatter",
      mode: "markers",
      name: config.label,
      x: items.map((row) => number(row.momentum_value)),
      y: items.map((row) => number(row.momentum_daily_change)),
      text: items.map((row) => displayName(row)),
      customdata: items.map((row) => [
        row.asset_code,
        row.current_momentum_state_duration,
        row.current_momentum_state_return,
        row.previous_momentum_state,
        row.momentum_change_label,
      ]),
      marker: { size: 9, color: config.color, opacity: 0.78, line: { width: 1, color: "#0b1018" } },
      hovertemplate:
        "标的=%{text}<br>代码=%{customdata[0]}<br>当前状态 bar=%{customdata[1]}<br>当前状态累积涨跌幅=%{customdata[2]:.2f}<br>此前状态=%{customdata[3]}<br>动能值=%{x:.4f}<br>相比前日=%{y:.4f}<br>%{customdata[4]}<extra></extra>",
    };
  });
  Plotly.newPlot(
    "momentumScatter",
    traces,
    {
      autosize: true,
      height: 620,
      margin: { l: 74, r: 24, t: 22, b: 64 },
      xaxis: { title: "动能数值", zeroline: false },
      yaxis: { title: "动能数值相比前日变动", zeroline: false },
      shapes: [
        { type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: 0, y1: 0, line: { color: "#d0d7de", width: 2 } },
        { type: "line", xref: "x", x0: 0, x1: 0, yref: "paper", y0: 0, y1: 1, line: { color: "#d0d7de", width: 2 } },
      ],
      legend: { orientation: "h" },
      dragmode: "pan",
    },
    { displayModeBar: true, displaylogo: false, responsive: true, scrollZoom: true }
  );
}

function renderSearch() {
  const snapshot = currentSnapshot();
  if (!snapshot) return;
  const query = state.search;
  const rows = currentCommodityRows(snapshot.latestRows || [])
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
    .map((row) => `<tr class="${rowNeedsHighlight(row) ? "bar-one" : ""}">${cols.map(([key]) => `<td>${formatCell(key, row)}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function formatCell(key, row) {
  if (key === "flag") return hasRelativeStateBarOne(row) ? `<span class="tag hot">比价bar=1</span>` : "";
  const value = row[key];
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (key === "decision") return `<span class="tag ${decisionClass(value)}">${escapeHtml(value)}</span>`;
  if (key === "relative_state_duration" && number(value) === 1) return `<span class="tag hot">1</span>`;
  if (key === "current_momentum_state_duration" && number(value) === 1) return `<span class="tag hot">1</span>`;
  if (key === "current_momentum_state") return `<span class="tag momentum-${momentumStateClass(value)}">${escapeHtml(value)}</span>`;
  if (key === "momentum_change_label") return `<span class="tag momentum-change">${escapeHtml(value)}</span>`;
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
      height: 430,
      margin: { l: 48, r: 20, t: 24, b: 44 },
      xaxis: { title: "相对强度 - 100", range: [-axis, axis], zeroline: false },
      yaxis: { title: "强度动量 - 100", range: [-axis, axis], zeroline: false, scaleanchor: "x", scaleratio: 1 },
      shapes: quadrantShapes(axis),
      annotations: quadrantAnnotations({ xAxis: axis, yAxis: axis, color: "rgba(128, 91, 0, 0.38)", size: 13 }).concat(
        chartTitleAnnotation(title)
      ),
      showlegend: false,
    },
    { displayModeBar: false, responsive: true }
  );
}

function quadrantAssetLabel(item) {
  return [text(item.displayName), text(item.assetCode)].filter(Boolean).join(" ");
}

function chartTitleAnnotation(title) {
  return {
    text: escapeHtml(title),
    x: 0.02,
    y: 0.98,
    xref: "paper",
    yref: "paper",
    xanchor: "left",
    yanchor: "top",
    showarrow: false,
    font: { size: 12, color: "rgba(31, 35, 40, 0.30)" },
  };
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

function marketSymbolForRow(row) {
  const meta = domesticFuturesMetaForRow(row);
  return text(meta?.marketSymbol);
}

function domesticFuturesMetaForRow(row) {
  const items = state.data?.futuresByDate?.[state.date] || [];
  const key = text(row.asset_key);
  const code = text(row.asset_code);
  return items.find((item) => (key && text(item.assetKey) === key) || (code && text(item.assetCode) === code)) || null;
}

function drawLiveMinuteKline(elementId, row) {
  const marketSymbol = marketSymbolForRow(row);
  if (!marketSymbol) {
    setChartMessage(elementId, "暂无实时分钟K映射");
    return;
  }
  setChartMessage(elementId, "实时分钟K加载中...");
  loadSinaMinuteBars(marketSymbol, "5")
    .then((bars) => {
      if (!bars.length) {
        setChartMessage(elementId, "暂无实时分钟K数据");
        return;
      }
      drawKline(elementId, bars.slice(-240), `${displayName(row)} 实时分钟K`);
    })
    .catch(() => setChartMessage(elementId, "实时分钟K加载失败"));
}

function loadSinaMinuteBars(marketSymbol, period = "5") {
  if (typeof document.createElement !== "function" || !document.head) return Promise.resolve([]);
  const callback = `sinaKline${Date.now()}${Math.floor(Math.random() * 100000)}`;
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = sinaMinuteKlineUrl(marketSymbol, period, callback);
    script.async = true;
    script.onload = () => {
      const rows = globalThis[callback] || [];
      delete globalThis[callback];
      script.remove();
      resolve(normalizeSinaMinuteBars(rows));
    };
    script.onerror = () => {
      delete globalThis[callback];
      script.remove();
      reject(new Error("sina minute kline load failed"));
    };
    document.head.appendChild(script);
  });
}

function sinaMinuteKlineUrl(marketSymbol, period = "5", callback = "callback") {
  const symbol = text(marketSymbol).replace(".CNFUT", "").split(".", 1)[0];
  return `https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20${encodeURIComponent(callback)}=/InnerFuturesNewService.getFewMinLine?symbol=${encodeURIComponent(symbol)}&type=${encodeURIComponent(period)}`;
}

function normalizeSinaMinuteBars(rows) {
  return (Array.isArray(rows) ? rows : [])
    .map((row) => ({
      bar_date: text(row.datetime || row.date),
      open: optionalNumber(row.open),
      high: optionalNumber(row.high),
      low: optionalNumber(row.low),
      close: optionalNumber(row.close),
      volume: optionalNumber(row.volume),
    }))
    .filter((row) => row.bar_date && row.open !== null && row.high !== null && row.low !== null && row.close !== null);
}

function setChartMessage(elementId, message) {
  const target = document.querySelector(`#${elementId}`);
  if (target) target.innerHTML = `<div class="empty chart-empty">${escapeHtml(message)}</div>`;
}

function chartDomId(selector, row, index, suffix) {
  return `${selector.replace(/[^a-zA-Z0-9]/g, "")}-${slug(row.asset_code)}-${index}-${suffix}`;
}

function relativeStatePoint(row) {
  const stateConfig = RELATIVE_STATE_QUADRANTS[text(row.relative_state).toLowerCase()];
  const duration = optionalNumber(row.relative_state_duration);
  const returnValue = optionalNumber(row.relative_state_return);
  if (!stateConfig || duration === null || returnValue === null) return null;
  return {
    x: stateConfig.xSign * Math.abs(duration),
    y: stateConfig.ySign * Math.abs(returnValue),
    direction: returnValue >= 0 ? "up" : "down",
    quadrant: stateConfig.label,
    duration: Math.abs(duration),
    returnValue,
  };
}

function mirroredAxis(values, minOuter) {
  const outer = niceAxisOuter(Math.max(...values, minOuter));
  const middle = niceAxisTick(outer / 2);
  return {
    range: [-outer, outer],
    tickvals: [-outer, -middle, 0, middle, outer],
    ticktext: [formatTick(outer), formatTick(middle), "0", formatTick(middle), formatTick(outer)],
    zeroline: false,
  };
}

function niceAxisOuter(value) {
  if (!Number.isFinite(value) || value <= 0) return 1;
  return niceAxisTick(value * 1.15);
}

function niceAxisTick(value) {
  if (value >= 20) return Math.ceil(value / 5) * 5;
  if (value >= 5) return Math.ceil(value);
  if (value >= 1) return Math.ceil(value * 2) / 2;
  return Math.ceil(value * 10) / 10;
}

function formatTick(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function quadrantShapes(axis) {
  return quadrantShapesXY(axis, axis);
}

function quadrantShapesXY(xAxis, yAxis, options = {}) {
  const axisLine = { color: options.axisColor || "#111111", dash: "solid", width: options.axisWidth || 5 };
  const zeroAxes = options.fullZeroAxes
    ? [
        { type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: 0, y1: 0, layer: "above", line: axisLine },
        { type: "line", xref: "x", x0: 0, x1: 0, yref: "paper", y0: 0, y1: 1, layer: "above", line: axisLine },
      ]
    : [
        { type: "line", x0: -xAxis, x1: xAxis, y0: 0, y1: 0, layer: "above", line: axisLine },
        { type: "line", x0: 0, x1: 0, y0: -yAxis, y1: yAxis, layer: "above", line: axisLine },
      ];
  return [
    [0, 0, xAxis, yAxis, "rgba(46,160,67,0.08)"],
    [-xAxis, 0, 0, yAxis, "rgba(9,105,218,0.08)"],
    [-xAxis, -yAxis, 0, 0, "rgba(207,34,46,0.07)"],
    [0, -yAxis, xAxis, 0, "rgba(191,135,0,0.08)"],
  ].map(([x0, y0, x1, y1, fillcolor]) => ({ type: "rect", x0, y0, x1, y1, fillcolor, line: { width: 0 }, layer: "below" }))
    .concat(zeroAxes);
}

function quadrantAnnotations(options = {}) {
  const color = options.color || "rgba(154, 103, 0, 0.74)";
  const size = options.size || 13;
  const usesDataCoordinates = Number.isFinite(options.xAxis) && Number.isFinite(options.yAxis);
  const items = usesDataCoordinates
    ? [
        { text: "Improving", x: -options.xAxis * 0.58, y: options.yAxis * 0.82 },
        { text: "Leading", x: options.xAxis * 0.58, y: options.yAxis * 0.82 },
        { text: "Lagging", x: -options.xAxis * 0.58, y: -options.yAxis * 0.82 },
        { text: "Weakening", x: options.xAxis * 0.58, y: -options.yAxis * 0.82 },
      ]
    : [
        { text: "Improving", x: 0.06, y: 0.94 },
        { text: "Leading", x: 0.94, y: 0.94 },
        { text: "Lagging", x: 0.06, y: 0.06 },
        { text: "Weakening", x: 0.94, y: 0.06 },
      ];
  return items.map((item) => ({
    ...item,
    xref: usesDataCoordinates ? "x" : "paper",
    yref: usesDataCoordinates ? "y" : "paper",
    showarrow: false,
    font: { size, color },
  }));
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

function trendBarValue(row, period) {
  if (!row) return null;
  const trend = row[`${period}_trend`];
  const duration = number(row[`${period}_trend_duration`]);
  if (isUp(trend)) return duration;
  if (isDown(trend)) return -duration;
  return 0;
}

function periodLabel(period) {
  return { day: "日K", week: "周K", month: "月K" }[period] || period;
}

function selectedCoreDate() {
  return state.date || (state.data?.datesByType?.core || []).at(-1) || "";
}

function selectedView() {
  return VIEW_KEYS.includes(state.activeView) ? state.activeView : "overview";
}

function selectView(view) {
  if (!VIEW_KEYS.includes(view)) return;
  state.activeView = view;
  if (document.body) document.body.dataset.activeView = view;
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.classList.toggle("active", button.dataset.viewTarget === view);
  });
  if (view === "early") {
    requestAnimationFrame(() => {
      const chart = document.querySelector("#relativeCrossSection");
      if (chart && globalThis.Plotly?.Plots?.resize) Plotly.Plots.resize(chart);
    });
  }
  if (view === "momentum") {
    requestAnimationFrame(() => {
      const chart = document.querySelector("#momentumScatter");
      if (chart && globalThis.Plotly?.Plots?.resize) Plotly.Plots.resize(chart);
    });
  }
}

function selectedQuadrantGroup() {
  return REQUIRED_FUTURES_GROUPS.includes(state.quadrantGroup) ? state.quadrantGroup : REQUIRED_FUTURES_GROUPS[0];
}

function selectQuadrantGroup(group) {
  if (!REQUIRED_FUTURES_GROUPS.includes(group)) return;
  state.quadrantGroup = group;
  renderMonthlyTrajectories();
}

function selectedTrendGroup() {
  return REQUIRED_FUTURES_GROUPS.includes(state.trendGroup) ? state.trendGroup : REQUIRED_FUTURES_GROUPS[0];
}

function selectTrendGroup(group) {
  if (!REQUIRED_FUTURES_GROUPS.includes(group)) return;
  state.trendGroup = group;
  renderTrendBars();
}

function rowMatchesFuturesItem(row, item) {
  return text(row.asset_key) === text(item.assetKey) || text(row.asset_code) === text(item.assetCode);
}

function futuresDisplayName(item) {
  return text(item.displayName) || text(item.assetName) || text(item.assetCode);
}

function coreDatesInLast30Days(dateText) {
  const cutoff = monthCutoff(dateText);
  return (state.data?.datesByType?.core || []).filter((date) => date >= cutoff && date <= dateText);
}

function monthCutoff(dateText) {
  const [year, month, day] = String(dateText).split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() - 30);
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
  return ["relative_state_duration", "day_trend_duration", "capital_state_duration"].some((key) => number(row[key]) === 1);
}

function hasRelativeStateBarOne(row) {
  return number(row.relative_state_duration) === 1;
}

function rowNeedsHighlight(row) {
  return hasRelativeStateBarOne(row) || number(row.current_momentum_state_duration) === 1;
}

function momentumStateClass(value) {
  return momentumStateKind({ current_momentum_state: value }) || "neutral";
}

function momentumStateKind(row) {
  const value = text(row?.current_momentum_state);
  if (["正", "正动能"].includes(value)) return "positive";
  if (["负", "负动能"].includes(value)) return "negative";
  if (value === "打点") return "dot";
  return "";
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

function optionalNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
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

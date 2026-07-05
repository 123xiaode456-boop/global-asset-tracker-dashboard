const state = {
  data: null,
  datasetKey: "all",
  date: "",
  search: "",
};

const columns = {
  opportunity: [
    ["rank", "排名"],
    ["score", "分数"],
    ["asset_code", "代码"],
    ["asset_name_cn", "中文名"],
    ["asset_name", "英文名"],
    ["decision_label", "结论"],
    ["relative_state", "比价"],
    ["capital_state", "资金"],
    ["reasons", "理由"],
  ],
  watch: [
    ["asset_code", "代码"],
    ["asset_name_cn", "中文名"],
    ["asset_name", "英文名"],
    ["day_trend", "日趋势"],
    ["week_trend", "周趋势"],
    ["relative_state", "比价"],
    ["capital_state", "资金"],
    ["relative_strength", "相对强度"],
    ["strength_momentum", "强度动量"],
  ],
  assets: [
    ["asset_code", "代码"],
    ["asset_name_cn", "中文名"],
    ["asset_name", "英文名"],
    ["dataset_type", "数据集"],
    ["day_trend", "日趋势"],
    ["week_trend", "周趋势"],
    ["month_trend", "月趋势"],
    ["relative_state", "比价"],
    ["capital_state", "资金"],
    ["relative_strength", "相对强度"],
    ["strength_momentum", "强度动量"],
    ["capital_value", "资金值"],
  ],
};

const groupColors = {
  "化工品": "#0969da",
  "贵金属": "#bf8700",
  "有色": "#2da44e",
  "农产品": "#cf222e",
};

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
  datasetSelect.value = state.datasetKey;
  datasetSelect.addEventListener("change", () => {
    state.datasetKey = datasetSelect.value;
    const dates = datesForCurrentDataset();
    state.date = dates[dates.length - 1] || "";
    syncDateSelect();
    render();
  });

  const dates = datesForCurrentDataset();
  state.date = dates[dates.length - 1] || "";
  syncDateSelect();

  document.querySelector("#assetSearch").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderTables();
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
  document.querySelector("#generatedAt").textContent = `数据生成：${state.data.generatedAt}`;
  if (!snapshot) {
    document.querySelector("main").innerHTML = `<section class="empty">当前筛选条件下没有数据。</section>`;
    return;
  }
  renderMetrics(snapshot);
  renderTables();
  renderFutures();
}

function renderMetrics(snapshot) {
  const counts = snapshot.latestCounts || {};
  const items = [
    ["日期", snapshot.latestDate || "-"],
    ["标的", counts.total || 0],
    ["加杠杆", counts.capital_add || 0],
    ["去杠杆", counts.capital_reduce || 0],
    ["重点观察", (snapshot.focusWatch || []).length],
  ];
  document.querySelector("#metrics").innerHTML = items
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderTables() {
  const snapshot = currentSnapshot();
  if (!snapshot) return;
  document.querySelector("#longTable").innerHTML = tableHtml(snapshot.longOpportunities || [], columns.opportunity);
  document.querySelector("#shortTable").innerHTML = tableHtml(snapshot.shortOpportunities || [], columns.opportunity);
  document.querySelector("#focusTable").innerHTML = tableHtml(snapshot.focusWatch || [], columns.watch);
  document.querySelector("#riskTable").innerHTML = tableHtml(snapshot.riskWatch || [], columns.watch);

  const filtered = (snapshot.latestRows || []).filter((row) => {
    if (!state.search) return true;
    return [row.asset_code, row.asset_name_cn, row.asset_name, row.asset_key]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(state.search);
  });
  document.querySelector("#assetTable").innerHTML = tableHtml(filtered, columns.assets);
}

function tableHtml(rows, tableColumns) {
  if (!rows.length) return `<div class="empty">暂无数据</div>`;
  const head = tableColumns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = tableColumns
        .map(([key]) => `<td class="${key === "reasons" ? "reason" : ""}">${formatCell(key, row[key])}</td>`)
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function formatCell(key, value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  const text = escapeHtml(String(value));
  if (key === "decision_label") {
    const cls = text.includes("多") ? "long" : text.includes("空") ? "short" : "";
    return `<span class="tag ${cls}">${text}</span>`;
  }
  if (key === "capital_state") return `<span class="tag capital">${text}</span>`;
  return text;
}

function renderFutures() {
  const container = document.querySelector("#futuresCharts");
  const futures = state.data.futuresByDate[state.date] || [];
  if (!futures.length) {
    container.innerHTML = `<div class="empty">当前日期没有核心数据集期货四象限轨迹。</div>`;
    return;
  }

  const groups = {};
  for (const item of futures) {
    if (!groups[item.group]) groups[item.group] = [];
    groups[item.group].push(item);
  }

  container.innerHTML = Object.entries(groups)
    .map(([group, items]) => {
      const cards = items
        .map((item, index) => {
          const id = chartId(group, item.assetCode, index);
          return `<div class="chart-card">
            <div class="chart-title"><span>${escapeHtml(item.displayName)}</span><code>${escapeHtml(item.assetCode)}</code></div>
            <div class="chart" id="${id}"></div>
          </div>`;
        })
        .join("");
      return `<div class="group-title">${escapeHtml(group)}</div><div class="chart-grid">${cards}</div>`;
    })
    .join("");

  requestAnimationFrame(() => {
    for (const [group, items] of Object.entries(groups)) {
      items.forEach((item, index) => drawQuadrant(chartId(group, item.assetCode, index), item));
    }
  });
}

function drawQuadrant(elementId, item) {
  const points = item.points || [];
  const values = points.flatMap((point) => [Math.abs(point.x), Math.abs(point.y)]).filter(Number.isFinite);
  const axis = Math.max(10, Math.max(...values, 0) * 1.2);
  const color = groupColors[item.group] || "#8c959f";
  const trace = {
    x: points.map((point) => point.x),
    y: points.map((point) => point.y),
    mode: "lines+markers+text",
    text: points.map((_, index) => (index === points.length - 1 ? item.displayName : "")),
    textposition: "top center",
    line: { color, width: 2 },
    marker: { color, size: points.map((_, index) => (index === points.length - 1 ? 11 : 6)) },
    customdata: points.map((point) => [point.date, point.quadrant, point.relativeState]),
    hovertemplate: "日期=%{customdata[0]}<br>象限=%{customdata[1]}<br>相对强度-100=%{x:.2f}<br>强度动量-100=%{y:.2f}<extra></extra>",
  };
  const layout = {
    margin: { l: 36, r: 16, t: 8, b: 36 },
    showlegend: false,
    xaxis: { title: "相对强度 - 100", range: [-axis, axis], zeroline: false },
    yaxis: { title: "强度动量 - 100", range: [-axis, axis], zeroline: false, scaleanchor: "x", scaleratio: 1 },
    shapes: quadrantShapes(axis),
    annotations: quadrantAnnotations(),
  };
  Plotly.newPlot(elementId, [trace], layout, { displayModeBar: false, responsive: true });
}

function quadrantShapes(axis) {
  return [
    [0, 0, axis, axis, "rgba(46,160,67,0.08)"],
    [-axis, 0, 0, axis, "rgba(9,105,218,0.08)"],
    [-axis, -axis, 0, 0, "rgba(207,34,46,0.07)"],
    [0, -axis, axis, 0, "rgba(191,135,0,0.08)"],
  ].map(([x0, y0, x1, y1, fillcolor]) => ({
    type: "rect",
    x0,
    y0,
    x1,
    y1,
    fillcolor,
    line: { width: 0 },
    layer: "below",
  })).concat([
    { type: "line", x0: -axis, x1: axis, y0: 0, y1: 0, line: { color: "#9a6700", dash: "dash", width: 1 } },
    { type: "line", x0: 0, x1: 0, y0: -axis, y1: axis, line: { color: "#9a6700", dash: "dash", width: 1 } },
  ]);
}

function quadrantAnnotations() {
  return [
    ["Improving", 0.08, 0.92],
    ["Leading", 0.9, 0.92],
    ["Lagging", 0.08, 0.08],
    ["Weakening", 0.88, 0.08],
  ].map(([text, x, y]) => ({ text, x, y, xref: "paper", yref: "paper", showarrow: false, font: { size: 11, color: "#9a6700" } }));
}

function chartId(group, code, index) {
  return `chart-${slug(group)}-${slug(code)}-${index}`;
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

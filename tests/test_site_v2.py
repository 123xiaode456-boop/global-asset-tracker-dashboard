import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"


def test_site_v2_index_cache_busts_app_script():
    html = (PROJECT_ROOT / "site-v2" / "index.html").read_text(encoding="utf-8")

    assert '<script src="./app.js?v=20260719-momentum-domestic-main"></script>' in html


def test_site_v2_frontend_rules_with_node():
    script = r"""
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

let source = fs.readFileSync(process.argv[1], "utf8");
source = source.replace(/\nmain\(\)\.catch\([\s\S]*?\);\s*$/, "\n");

const context = {
  console,
  location: { hostname: "123xiaode456-boop.github.io" },
  __plots: [],
  __resizes: [],
  __elements: {},
  __body: { dataset: {}, classList: { toggle: () => {} } },
  Plotly: {
    newPlot: (...args) => {
      context.__plots.push(args);
    },
    Plots: {
      resize: (target) => {
        context.__resizes.push(target);
      },
    },
  },
  document: {
    body: null,
    querySelector: (selector) => {
      if (!context.__elements[selector]) {
        context.__elements[selector] = {
          innerHTML: "",
          textContent: "",
          value: "",
          dataset: {},
          classList: { toggle: () => {} },
        };
      }
      return context.__elements[selector];
    },
    querySelectorAll: () => [],
  },
  requestAnimationFrame: (fn) => fn(),
};
context.document.body = context.__body;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(
  source +
    `
globalThis.__api = {
  state,
  currentCommodityRows,
  render,
  barAlertRows,
  barOneReasons,
  filterLong,
  filterShort,
  filterEarlyRows,
  setEarlySearch,
  resetEarlySearch,
  sortPreview,
  hasAnyBarOne,
  hasRelativeStateBarOne,
  decisionLabel,
  monthCutoff,
  selectedCoreDate,
  coreDatesInLast30Days,
  renderRelativeCrossSection,
  relativeStatePoint,
  selectedView,
  selectView,
  selectedQuadrantGroup,
  selectQuadrantGroup,
  renderMonthlyTrajectories,
  selectedTrendGroup,
  selectTrendGroup,
  renderTrendBars,
  momentumRowsForCurrentDate,
  filterMomentumRows,
  setMomentumSearch,
  setMomentumState,
  momentumStrengthLabel,
  rankMomentumRows,
  renderMomentum,
  drawKline,
  domesticCommodityRows,
  marketSymbolForRow,
  sinaMinuteKlineUrl,
  normalizeSinaMinuteBars,
  priceHistory,
  toWeeklyBars,
  SEARCH_COLUMNS,
  MA_WINDOWS,
  DATA_URL,
  currentDataUrl,
};`,
  context
);

const api = context.__api;
assert.strictEqual(api.DATA_URL, "./data/app-data.json");
assert.ok(api.currentDataUrl().startsWith("./data/app-data.json?v="));
const up = "上行趋势";
const down = "下行趋势";
const base = {
  asset_name: "Alpha",
  capital_state: "加杠杆",
  day_trend: up,
  week_trend: up,
  month_trend: up,
  relative_state: "lead",
  relative_state_duration: 2,
  capital_state_duration: 3,
  day_trend_duration: 4,
  week_trend_duration: 5,
  month_trend_duration: 6,
};
const rows = [
  { ...base, asset_code: "B", relative_state_duration: 2, capital_state_duration: 4, day_trend_duration: 1 },
  { ...base, asset_code: "A", relative_state_duration: 1, capital_state_duration: 9, day_trend_duration: 9 },
  { ...base, asset_code: "C", relative_state_duration: 2, capital_state_duration: 3, day_trend_duration: 9 },
  { ...base, asset_code: "D", relative_state: "weakening", capital_state: "去杠杆", day_trend: down, week_trend: down },
  { ...base, asset_code: "E", relative_state: "lead", capital_state: "去杠杆" },
];

assert.strictEqual(JSON.stringify(api.filterLong(rows).map((row) => row.asset_code)), JSON.stringify(["B", "A", "C"]));
assert.strictEqual(JSON.stringify(api.filterShort(rows).map((row) => row.asset_code)), JSON.stringify(["D"]));
assert.strictEqual(JSON.stringify(api.sortPreview(rows.slice(0, 3)).map((row) => row.asset_code)), JSON.stringify(["A", "B", "C"]));
assert.strictEqual(api.hasAnyBarOne({ ...base, day_trend_duration: 8, week_trend_duration: 1 }), false);
assert.strictEqual(api.hasAnyBarOne({ ...base, day_trend_duration: 1, week_trend_duration: 8 }), true);
assert.strictEqual(api.hasRelativeStateBarOne({ ...base, relative_state_duration: 1 }), true);
assert.strictEqual(api.hasRelativeStateBarOne({ ...base, relative_state_duration: 2, day_trend_duration: 1 }), false);
assert.strictEqual(api.decisionLabel(rows[0]), "可做多");
assert.strictEqual(api.decisionLabel(rows[3]), "可做空");
assert.strictEqual(api.decisionLabel(rows[4]), "观望");
assert.strictEqual(api.monthCutoff("2026-06-22"), "2026-05-23");
const leadDownPoint = api.relativeStatePoint({ relative_state: "lead", relative_state_duration: 3, relative_state_return: -2.5 });
assert.strictEqual(leadDownPoint.x, 3);
assert.strictEqual(leadDownPoint.y, 2.5);
assert.strictEqual(leadDownPoint.direction, "down");
assert.strictEqual(leadDownPoint.quadrant, "Leading");
const improvingUpPoint = api.relativeStatePoint({ relative_state: "improving", relative_state_duration: 4, relative_state_return: 1.25 });
assert.strictEqual(improvingUpPoint.x, -4);
assert.strictEqual(improvingUpPoint.y, 1.25);
assert.strictEqual(improvingUpPoint.direction, "up");
assert.strictEqual(improvingUpPoint.quadrant, "Improving");
const lagUpPoint = api.relativeStatePoint({ relative_state: "Lag", relative_state_duration: 5, relative_state_return: 0.8 });
assert.strictEqual(lagUpPoint.x, -5);
assert.strictEqual(lagUpPoint.y, -0.8);
assert.strictEqual(lagUpPoint.direction, "up");
assert.strictEqual(lagUpPoint.quadrant, "Lagging");
const weakeningDownPoint = api.relativeStatePoint({ relative_state: "Weakening", relative_state_duration: 6, relative_state_return: -1.7 });
assert.strictEqual(weakeningDownPoint.x, 6);
assert.strictEqual(weakeningDownPoint.y, -1.7);
assert.strictEqual(weakeningDownPoint.direction, "down");
assert.strictEqual(weakeningDownPoint.quadrant, "Weakening");

context.__plots = [];
api.renderRelativeCrossSection([
  { asset_code: "L", asset_name: "Lead", relative_state: "lead", relative_state_duration: 3, relative_state_return: 2.5 },
  { asset_code: "I", asset_name: "Improve", relative_state: "improving", relative_state_duration: 4, relative_state_return: -1.25 },
  { asset_code: "G", asset_name: "Lag", relative_state: "lag", relative_state_duration: 5, relative_state_return: 0.8 },
  { asset_code: "W", asset_name: "Weak", relative_state: "weakening", relative_state_duration: 6, relative_state_return: -1.7 },
]);
const relativePlot = context.__plots.at(-1);
assert.strictEqual(relativePlot[0], "relativeCrossSection");
assert.strictEqual(JSON.stringify(relativePlot[1].map((trace) => trace.name)), JSON.stringify(["上涨", "下跌", "上涨标的名称", "下跌标的名称"]));
assert.strictEqual(JSON.stringify(relativePlot[1][0].x), JSON.stringify([3, -5]));
assert.strictEqual(JSON.stringify(relativePlot[1][0].y), JSON.stringify([2.5, -0.8]));
assert.strictEqual(JSON.stringify(relativePlot[1][1].x), JSON.stringify([-4, 6]));
assert.strictEqual(JSON.stringify(relativePlot[1][1].y), JSON.stringify([1.25, -1.7]));
assert.strictEqual(relativePlot[1][0].mode, "markers");
assert.strictEqual(relativePlot[1][1].mode, "markers");
assert.strictEqual(relativePlot[1][2].mode, "text");
assert.strictEqual(relativePlot[1][3].mode, "text");
assert.strictEqual(JSON.stringify(relativePlot[1][2].x), JSON.stringify(relativePlot[1][0].x));
assert.strictEqual(JSON.stringify(relativePlot[1][2].y), JSON.stringify(relativePlot[1][0].y));
assert.strictEqual(JSON.stringify(relativePlot[1][3].x), JSON.stringify(relativePlot[1][1].x));
assert.strictEqual(JSON.stringify(relativePlot[1][3].y), JSON.stringify(relativePlot[1][1].y));
assert.ok(relativePlot[1][2].showlegend === false && relativePlot[1][3].showlegend === false);
assert.strictEqual(relativePlot[1][2].textposition, "middle center");
assert.strictEqual(relativePlot[1][3].textposition, "middle center");
assert.strictEqual(relativePlot[1][2].cliponaxis, true);
assert.strictEqual(relativePlot[1][3].cliponaxis, true);
assert.ok(relativePlot[1][2].textfont.color.includes("0.38"));
assert.ok(relativePlot[1][3].textfont.color.includes("0.38"));
assert.strictEqual(relativePlot[2].xaxis.title, "当前比价状态持续时间（左右均为正值）");
assert.strictEqual(relativePlot[2].yaxis.title, "当前比价状态涨跌幅绝对值（上下均为正值）");
assert.strictEqual(relativePlot[2].dragmode, "pan");
assert.strictEqual(relativePlot[3].scrollZoom, true);
assert.strictEqual(relativePlot[3].displayModeBar, true);
assert.strictEqual(relativePlot[2].autosize, true);
assert.ok(relativePlot[2].height >= 740);
assert.ok(relativePlot[2].shapes.length >= 6);
const axisLines = relativePlot[2].shapes.filter((shape) => shape.type === "line");
assert.ok(axisLines.every((shape) => shape.layer === "above"));
assert.ok(axisLines.every((shape) => shape.line.dash === "solid"));
assert.ok(axisLines.every((shape) => shape.line.color === "#111111"));
assert.ok(axisLines.every((shape) => shape.line.width >= 4 && shape.line.width <= 6));
assert.ok(axisLines.some((shape) => shape.xref === "paper" && shape.x0 === 0 && shape.x1 === 1 && shape.yref === "y" && shape.y0 === 0 && shape.y1 === 0));
assert.ok(axisLines.some((shape) => shape.xref === "x" && shape.x0 === 0 && shape.x1 === 0 && shape.yref === "paper" && shape.y0 === 0 && shape.y1 === 1));
const earlyRows = [
  { asset_code: "CU1!", asset_name_cn: "铜期货", asset_name: "Copper Futures", asset_key: "CU1!|Copper Futures", relative_state: "lead", relative_state_duration: 3, relative_state_return: 2.5 },
  { asset_code: "AL1!", asset_name_cn: "铝期货", asset_name: "Aluminum Futures", asset_key: "AL1!|Aluminum Futures", relative_state: "improving", relative_state_duration: 4, relative_state_return: -1.25 },
];
api.state.earlySearch = "铜";
assert.strictEqual(JSON.stringify(api.filterEarlyRows(earlyRows).map((row) => row.asset_code)), JSON.stringify(["CU1!"]));
api.state.earlySearch = "aluminum";
assert.strictEqual(JSON.stringify(api.filterEarlyRows(earlyRows).map((row) => row.asset_code)), JSON.stringify(["AL1!"]));
api.state.earlySearch = "CU1";
assert.strictEqual(JSON.stringify(api.filterEarlyRows(earlyRows).map((row) => row.asset_code)), JSON.stringify(["CU1!"]));
api.state.earlySearch = "";
assert.strictEqual(api.filterEarlyRows(earlyRows).length, 2);
api.selectView("early");
assert.strictEqual(api.selectedView(), "early");
assert.strictEqual(context.document.body.dataset.activeView, "early");
assert.ok(context.__resizes.includes(context.__elements["#relativeCrossSection"]));
api.selectView("trajectory");
assert.strictEqual(api.selectedView(), "trajectory");
assert.strictEqual(context.document.body.dataset.activeView, "trajectory");

api.state.date = "2026-06-22";
api.state.data = {
  datesByType: {
    core: ["2026-05-20", "2026-05-23", "2026-06-01", "2026-06-10", "2026-06-22", "2026-07-03"],
  },
  snapshots: {
    "core|2026-05-23": {
      latestRows: [
        { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", day_trend: up, day_trend_duration: 1, week_trend: up, week_trend_duration: 2, month_trend: down, month_trend_duration: 3 },
        { asset_key: "CHEM2|Chem Two", asset_code: "CHEM2", day_trend: down, day_trend_duration: 4, week_trend: up, week_trend_duration: 5, month_trend: up, month_trend_duration: 6 },
        { asset_key: "GOLD1|Gold", asset_code: "GOLD1", day_trend: up, day_trend_duration: 7, week_trend: down, week_trend_duration: 8, month_trend: up, month_trend_duration: 9 },
      ],
    },
    "core|2026-06-01": {
      latestRows: [
        { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", day_trend: down, day_trend_duration: 2, week_trend: down, week_trend_duration: 3, month_trend: up, month_trend_duration: 4 },
        { asset_key: "CHEM2|Chem Two", asset_code: "CHEM2", day_trend: up, day_trend_duration: 5, week_trend: up, week_trend_duration: 6, month_trend: down, month_trend_duration: 7 },
        { asset_key: "GOLD1|Gold", asset_code: "GOLD1", day_trend: down, day_trend_duration: 8, week_trend: up, week_trend_duration: 9, month_trend: down, month_trend_duration: 10 },
      ],
    },
    "core|2026-06-10": {
      latestRows: [
        { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", day_trend: up, day_trend_duration: 1, week_trend: up, week_trend_duration: 2, month_trend: down, month_trend_duration: 3 },
        { asset_key: "CHEM2|Chem Two", asset_code: "CHEM2", day_trend: down, day_trend_duration: 4, week_trend: up, week_trend_duration: 5, month_trend: up, month_trend_duration: 6 },
        { asset_key: "GOLD1|Gold", asset_code: "GOLD1", day_trend: up, day_trend_duration: 7, week_trend: down, week_trend_duration: 8, month_trend: up, month_trend_duration: 9 },
      ],
    },
    "core|2026-06-22": {
      latestRows: [
        { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", day_trend: down, day_trend_duration: 2, week_trend: down, week_trend_duration: 3, month_trend: up, month_trend_duration: 4 },
        { asset_key: "CHEM2|Chem Two", asset_code: "CHEM2", day_trend: up, day_trend_duration: 5, week_trend: up, week_trend_duration: 6, month_trend: down, month_trend_duration: 7 },
        { asset_key: "GOLD1|Gold", asset_code: "GOLD1", day_trend: down, day_trend_duration: 8, week_trend: up, week_trend_duration: 9, month_trend: down, month_trend_duration: 10 },
      ],
    },
        "core|2026-07-03": {
          latestDate: "2026-07-03",
          latestRows: [
        { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", asset_name_cn: "化工一号", asset_name: "Chem One", relative_state: "lead", relative_state_duration: 3, relative_state_return: 2.5, capital_state: "加杠杆", day_trend: up, day_trend_duration: 3, week_trend: up, week_trend_duration: 4, month_trend: up, month_trend_duration: 5 },
        { asset_key: "CHEM2|Chem Two", asset_code: "CHEM2", asset_name_cn: "化工二号", asset_name: "Chem Two", relative_state: "lead", relative_state_duration: 5, relative_state_return: 1.5, capital_state: "加杠杆", day_trend: up, day_trend_duration: 6, week_trend: up, week_trend_duration: 7, month_trend: down, month_trend_duration: 8 },
        { asset_key: "FOREIGN1|Foreign", asset_code: "FOREIGN1", asset_name_cn: "海外原油", asset_name: "Foreign", relative_state: "lead", relative_state_duration: 4, relative_state_return: 1.2, capital_state: "加杠杆", day_trend: up, day_trend_duration: 5, week_trend: up, week_trend_duration: 6, month_trend: up, month_trend_duration: 7 },
        { asset_key: "SHORTDOM|Short Domestic", asset_code: "SHORTDOM", asset_name_cn: "做空国内", asset_name: "Short Domestic", relative_state: "lag", relative_state_duration: 2, relative_state_return: -1.1, capital_state: "去杠杆", day_trend: down, day_trend_duration: 2, week_trend: down, week_trend_duration: 3, month_trend: up, month_trend_duration: 4 },
        { asset_key: "GOLD1|Gold", asset_code: "GOLD1", day_trend: up, day_trend_duration: 9, week_trend: up, week_trend_duration: 10, month_trend: up, month_trend_duration: 11 },
        { asset_key: "UNMAPPED_LONG|Long", asset_code: "UNMAPPED_LONG", asset_name: "Unmapped Long", relative_state: "improving", capital_state: "加杠杆", day_trend: up, day_trend_duration: 2, week_trend: up, week_trend_duration: 3, month_trend: down, month_trend_duration: 4 },
        { asset_key: "UNMAPPED_SHORT|Short", asset_code: "UNMAPPED_SHORT", asset_name: "Unmapped Short", relative_state: "lag", capital_state: "去杠杆", day_trend: down, day_trend_duration: 2, week_trend: down, week_trend_duration: 3, month_trend: up, month_trend_duration: 4 },
        { asset_key: "NO_SIGNAL|No", asset_code: "NO_SIGNAL", asset_name: "No Signal", relative_state: "lead", capital_state: "去杠杆", day_trend: up, day_trend_duration: 2, week_trend: up, week_trend_duration: 3, month_trend: up, month_trend_duration: 4 },
      ],
    },
  },
  futuresByDate: {
    "2026-06-22": [
      { assetKey: "A|Alpha", assetCode: "A", group: "化工品" },
      { assetKey: "C|Alpha", assetCode: "C", group: "贵金属" },
    ],
    "2026-07-03": [
      {
        assetKey: "CHEM1|Chem One",
        assetCode: "CHEM1",
        displayName: "化工一号",
        group: "化工品",
        isDomestic: true,
        marketSymbol: "TA0.CNFUT",
        points: [{ date: "2026-07-03", x: 1, y: 2 }],
      },
      {
        assetKey: "CHEM2|Chem Two",
        assetCode: "CHEM2",
        displayName: "化工二号",
        group: "化工品",
        isDomestic: true,
        marketSymbol: "BR0.CNFUT",
        points: [{ date: "2026-07-03", x: 2, y: 3 }],
      },
      {
        assetKey: "FOREIGN1|Foreign",
        assetCode: "FOREIGN1",
        displayName: "海外原油",
        group: "化工品",
        isDomestic: false,
        points: [{ date: "2026-07-03", x: 3, y: 2 }],
      },
      {
        assetKey: "SHORTDOM|Short Domestic",
        assetCode: "SHORTDOM",
        displayName: "做空国内",
        group: "化工品",
        isDomestic: true,
        marketSymbol: "RU0.CNFUT",
        points: [{ date: "2026-07-03", x: -3, y: -2 }],
      },
      {
        assetKey: "GOLD1|Gold",
        assetCode: "GOLD1",
        displayName: "黄金",
        group: "贵金属",
        isDomestic: true,
        points: [{ date: "2026-07-03", x: 4, y: 5 }],
      },
    ],
  },
  momentumByDate: {
    "2026-07-03": [
      { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", asset_name_cn: "化工一号", asset_name: "Chem One", current_momentum_state_duration: 1, current_momentum_state: "正动能", current_momentum_state_return: 2.5, previous_momentum_state: "打点", previous_momentum_state_return: 0.2, momentum_value: 1.25, momentum_daily_change: 0.35 },
      { asset_key: "SHORTDOM|Short Domestic", asset_code: "SHORTDOM", asset_name_cn: "做空国内", asset_name: "Short Domestic", current_momentum_state_duration: 3, current_momentum_state: "负动能", current_momentum_state_return: -3.5, previous_momentum_state: "打点", previous_momentum_state_return: -0.2, momentum_value: -1.75, momentum_daily_change: -0.55 },
      { asset_key: "GOLD1|Gold", asset_code: "GOLD1", asset_name_cn: "黄金", asset_name: "Gold", current_momentum_state_duration: 2, current_momentum_state: "打点", current_momentum_state_return: 0.1, previous_momentum_state: "正动能", previous_momentum_state_return: 1.2, momentum_value: 0.02, momentum_daily_change: -0.01 },
    ],
  },
  priceHistories: {
    "CHEM1|Chem One": [
      { bar_date: "2026-07-01", open: 10, high: 11, low: 9, close: 10.5, volume: 100 },
      { bar_date: "2026-07-02", open: 10.5, high: 12, low: 10, close: 11.5, volume: 120 },
    ],
    "FOREIGN1|Foreign": [
      { bar_date: "2026-07-01", open: 20, high: 22, low: 19, close: 21, volume: 100 },
    ],
    "SHORTDOM|Short Domestic": [
      { bar_date: "2026-07-01", open: 30, high: 31, low: 28, close: 29, volume: 110 },
      { bar_date: "2026-07-02", open: 29, high: 30, low: 27, close: 28, volume: 130 },
    ],
  },
};
assert.strictEqual(api.selectedCoreDate(), "2026-06-22");
assert.strictEqual(JSON.stringify(api.coreDatesInLast30Days("2026-06-22")), JSON.stringify(["2026-05-23", "2026-06-01", "2026-06-10", "2026-06-22"]));
assert.strictEqual(JSON.stringify(api.currentCommodityRows([
  { ...rows[1], asset_key: "A|Alpha" },
  { ...rows[2], asset_key: "C|Alpha" },
  { ...rows[2], asset_code: "C", asset_key: "C|Wrong" },
]).map((row) => row.asset_key)), JSON.stringify(["A|Alpha", "C|Alpha"]));
api.state.date = "2026-07-03";
api.state.search = "";
context.__plots = [];
api.render();
assert.ok(context.__elements["#longMatrix"].innerHTML.includes(">CHEM1<"));
assert.ok(context.__elements["#longMatrix"].innerHTML.includes(">CHEM2<"));
assert.ok(context.__elements["#longMatrix"].innerHTML.includes(">FOREIGN1<"));
assert.ok(context.__elements["#longMatrix"].innerHTML.includes(">UNMAPPED_LONG<"));
assert.ok(context.__elements["#shortMatrix"].innerHTML.includes(">SHORTDOM<"));
assert.ok(context.__elements["#shortMatrix"].innerHTML.includes(">UNMAPPED_SHORT<"));
assert.ok(!context.__elements["#longMatrix"].innerHTML.includes(">NO_SIGNAL<"));
assert.ok(!context.__elements["#shortMatrix"].innerHTML.includes(">NO_SIGNAL<"));
assert.strictEqual(JSON.stringify(api.domesticCommodityRows(api.filterLong(api.state.data.snapshots["core|2026-07-03"].latestRows)).map((row) => row.asset_code)), JSON.stringify(["CHEM1", "CHEM2"]));
assert.ok(context.__elements["#longKlinePanel"].innerHTML.includes("国内商品期货行情K线"));
assert.ok(context.__elements["#longKlinePanel"].innerHTML.includes("实时分钟K"));
assert.ok(context.__elements["#longKlinePanel"].innerHTML.includes("化工一号"));
assert.ok(context.__elements["#longKlinePanel"].innerHTML.includes("化工二号"));
assert.ok(context.__elements["#longKlinePanel"].innerHTML.includes("缺行情标的"));
assert.ok(!context.__elements["#longKlinePanel"].innerHTML.includes("海外原油"));
assert.ok(!context.__elements["#longKlinePanel"].innerHTML.includes("Unmapped Long"));
assert.ok(context.__elements["#shortKlinePanel"].innerHTML.includes("做空国内"));
assert.ok(!context.__elements["#shortKlinePanel"].innerHTML.includes("Unmapped Short"));
assert.ok(context.__elements["#momentumPositiveRank"].innerHTML.includes("CHEM1"));
assert.ok(context.__elements["#momentumNegativeRank"].innerHTML.includes("SHORTDOM"));
assert.ok(context.__elements["#momentumNewStates"].innerHTML.includes("CHEM1"));
assert.ok(context.__elements["#momentumTable"].innerHTML.includes("GOLD1"));
assert.strictEqual(api.momentumStrengthLabel(api.momentumRowsForCurrentDate()[0]), "正动能增强");
assert.strictEqual(api.momentumStrengthLabel(api.momentumRowsForCurrentDate()[1]), "负动能增强");
assert.strictEqual(JSON.stringify(api.rankMomentumRows(api.momentumRowsForCurrentDate(), "positive").map((row) => row.asset_code)), JSON.stringify(["CHEM1"]));
api.setMomentumState("负动能");
assert.strictEqual(JSON.stringify(api.filterMomentumRows().map((row) => row.asset_code)), JSON.stringify(["SHORTDOM"]));
api.setMomentumState("all");
api.setMomentumSearch("黄金");
assert.strictEqual(JSON.stringify(api.filterMomentumRows().map((row) => row.asset_code)), JSON.stringify(["GOLD1"]));
api.setMomentumSearch("");
api.selectView("momentum");
assert.strictEqual(api.selectedView(), "momentum");
assert.ok(context.__resizes.includes(context.__elements["#momentumScatter"]));
assert.ok(context.__plots.some((plot) => plot[0].startsWith("longKlinePanel-") && plot[2].title.includes("化工一号")));
assert.ok(context.__plots.some((plot) => plot[0].startsWith("shortKlinePanel-") && plot[2].title.includes("做空国内")));
assert.strictEqual(api.marketSymbolForRow({ asset_key: "CHEM1|Chem One", asset_code: "CHEM1" }), "TA0.CNFUT");
assert.ok(api.sinaMinuteKlineUrl("TA0.CNFUT", "5", "testCallback").includes("var%20testCallback=/InnerFuturesNewService.getFewMinLine"));
assert.ok(api.sinaMinuteKlineUrl("TA0.CNFUT", "5", "testCallback").includes("symbol=TA0"));
assert.strictEqual(JSON.stringify(api.normalizeSinaMinuteBars([
  { datetime: "2026-07-08 09:05:00", open: "10", high: "11", low: "9", close: "10.5", volume: "1200" },
])), JSON.stringify([
  { bar_date: "2026-07-08 09:05:00", open: 10, high: 11, low: 9, close: 10.5, volume: 1200 },
]));
context.__plots = [];
api.setEarlySearch("化工一号");
assert.strictEqual(api.state.earlySearch, "化工一号");
assert.strictEqual(context.__elements["#earlyAssetSearch"].value, "化工一号");
assert.ok(context.__elements["#earlySearchStatus"].textContent.includes("1 / 5"));
const searchedEarlyPlot = context.__plots.at(-1);
assert.strictEqual(JSON.stringify(searchedEarlyPlot[1][0].x), JSON.stringify([3]));
assert.strictEqual(JSON.stringify(searchedEarlyPlot[1][0].text), JSON.stringify(["化工一号"]));
context.__plots = [];
api.resetEarlySearch();
assert.strictEqual(api.state.earlySearch, "");
assert.strictEqual(context.__elements["#earlyAssetSearch"].value, "");
assert.ok(context.__elements["#earlySearchStatus"].textContent.includes("5 / 5"));
const resetEarlyPlot = context.__plots.at(-1);
assert.strictEqual(resetEarlyPlot[1][0].x.length + resetEarlyPlot[1][1].x.length, 4);
context.__plots = [];
api.renderMonthlyTrajectories();
assert.strictEqual(api.selectedQuadrantGroup(), "化工品");
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("quadrant-tabs"));
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("quadrant-grid"));
assert.ok(!context.__elements["#monthlyTrajectories"].innerHTML.includes("黄金"));
assert.strictEqual(context.__plots.length, 4);
assert.strictEqual(JSON.stringify(context.__plots.map((plot) => plot[0])), JSON.stringify(["quadrant-化工品-0", "quadrant-化工品-1", "quadrant-化工品-2", "quadrant-化工品-3"]));
const quadrantLayout = context.__plots[0][2];
const quadrantLabels = quadrantLayout.annotations.slice(0, 4);
assert.strictEqual(JSON.stringify(quadrantLabels.map((item) => item.text)), JSON.stringify(["Improving", "Leading", "Lagging", "Weakening"]));
assert.strictEqual(JSON.stringify(quadrantLabels.map((item) => item.xref)), JSON.stringify(["x", "x", "x", "x"]));
assert.strictEqual(JSON.stringify(quadrantLabels.map((item) => item.yref)), JSON.stringify(["y", "y", "y", "y"]));
assert.strictEqual(JSON.stringify(quadrantLabels.map((item) => item.x)), JSON.stringify([-5.8, 5.8, -5.8, 5.8]));
assert.strictEqual(JSON.stringify(quadrantLabels.map((item) => item.y)), JSON.stringify([8.2, 8.2, -8.2, -8.2]));
assert.ok(quadrantLabels.every((item) => item.font.color === "rgba(128, 91, 0, 0.38)"));
assert.ok(quadrantLabels.every((item) => item.font.size >= 13));
const assetTitle = quadrantLayout.annotations[4];
assert.strictEqual(assetTitle.text, "化工一号 CHEM1");
assert.strictEqual(assetTitle.xref, "paper");
assert.strictEqual(assetTitle.yref, "paper");
assert.strictEqual(assetTitle.xanchor, "left");
assert.strictEqual(assetTitle.yanchor, "top");
assert.strictEqual(assetTitle.font.color, "rgba(31, 35, 40, 0.30)");
assert.ok(assetTitle.font.size <= 12);
assert.ok(!quadrantLayout.title);
api.selectQuadrantGroup("贵金属");
assert.strictEqual(api.selectedQuadrantGroup(), "贵金属");
assert.ok(!context.__elements["#monthlyTrajectories"].innerHTML.includes("化工一号"));
const goldLayout = context.__plots.at(-1)[2];
assert.strictEqual(goldLayout.annotations[4].text, "黄金 GOLD1");
context.__plots = [];
api.selectTrendGroup("化工品");
assert.strictEqual(api.selectedTrendGroup(), "化工品");
assert.ok(context.__elements["#trendBars"].innerHTML.includes("trend-tabs"));
assert.ok(context.__elements["#trendBars"].innerHTML.includes("trend-grid"));
assert.ok(context.__elements["#trendBars"].innerHTML.includes("化工一号"));
assert.ok(context.__elements["#trendBars"].innerHTML.includes("化工二号"));
assert.ok(!context.__elements["#trendBars"].innerHTML.includes("黄金"));
assert.strictEqual(context.__plots.length, 4);
assert.strictEqual(JSON.stringify(context.__plots.map((plot) => plot[0])), JSON.stringify(["trend-化工品-0", "trend-化工品-1", "trend-化工品-2", "trend-化工品-3"]));
assert.strictEqual(JSON.stringify(context.__plots[0][1].map((trace) => trace.name)), JSON.stringify(["日K", "周K", "月K"]));
assert.strictEqual(JSON.stringify(context.__plots[0][1][0].y), JSON.stringify([1, -2, 3]));
api.selectTrendGroup("贵金属");
assert.strictEqual(api.selectedTrendGroup(), "贵金属");
assert.ok(context.__elements["#trendBars"].innerHTML.includes("黄金"));
assert.ok(!context.__elements["#trendBars"].innerHTML.includes("化工一号"));
assert.strictEqual(JSON.stringify(api.barAlertRows(rows).map((row) => row.asset_code)), JSON.stringify(["A", "B"]));
assert.strictEqual(JSON.stringify(api.barOneReasons({ ...base, relative_state_duration: 1, day_trend_duration: 1, capital_state_duration: 1 })), JSON.stringify(["比价=1", "日K=1", "资金=1"]));
assert.strictEqual(JSON.stringify(api.SEARCH_COLUMNS.map((item) => item[0])), JSON.stringify([
  "asset_code",
  "asset_name_cn",
  "asset_name",
  "decision",
  "relative_state_duration",
  "relative_state",
  "relative_state_return",
  "day_trend",
  "day_trend_duration",
  "week_trend",
  "week_trend_duration",
  "month_trend",
  "month_trend_duration",
  "capital_state_duration",
  "capital_state",
]));
assert.strictEqual(JSON.stringify(api.MA_WINDOWS), JSON.stringify([5, 10, 20, 60, 250]));

api.state.data = {
  priceHistories: {
    "AAA|Alpha": [{ bar_date: "2026-06-01", open: 1, high: 2, low: 1, close: 2, volume: 10 }],
    BBB: [{ bar_date: "2026-06-02", open: 2, high: 3, low: 2, close: 3, volume: 20 }],
  },
};
assert.strictEqual(api.priceHistory({ asset_key: "AAA|Alpha", asset_code: "AAA", asset_name: "Alpha" }).length, 1);
assert.strictEqual(api.priceHistory({ asset_code: "BBB", asset_name: "Beta" }).length, 1);

const bars = Array.from({ length: 260 }, (_, index) => ({
  bar_date: new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10),
  open: 100 + index,
  high: 101 + index,
  low: 99 + index,
  close: 100.5 + index,
  volume: 1000 + index,
}));
api.drawKline("chart", bars, "日K");
const traceNames = context.__plots.at(-1)[1].map((trace) => trace.name);
assert.strictEqual(JSON.stringify(traceNames), JSON.stringify(["K线", "MA5", "MA10", "MA20", "MA60", "MA250"]));
assert.ok(api.toWeeklyBars(bars).length < bars.length);
"""
    subprocess.run([str(NODE), "-e", script, str(PROJECT_ROOT / "site-v2" / "app.js")], check=True)


def test_site_v2_styles_support_kline_and_missing_panels():
    css = (PROJECT_ROOT / "site-v2" / "styles.css").read_text(encoding="utf-8")

    for selector in [
        ".module-nav",
        ".module-button",
        "body[data-active-view",
        ".kline-summary",
        ".missing",
        ".kline-grid",
        ".kline-card",
        ".kline-chart",
        ".quadrant-tabs",
        ".quadrant-grid",
        ".quadrant-card",
        ".quadrant-chart",
        ".trend-grid",
        ".trend-card",
        ".trend-chart",
        ".momentum-controls",
        ".momentum-chart",
        ".momentum-rank-grid",
    ]:
        assert selector in css

    assert "#0b1018" in css
    assert "#00d4ff" in css
    assert "#relativeCrossSection" in css
    assert "body[data-active-view=\"early\"] main" in css
    assert "padding: 12px 8px 48px" in css
    assert "min-height: 760px" in css
    assert "height: 760px" in css
    assert "width: 100%" in css


def test_site_v2_index_uses_module_navigation():
    html = (PROJECT_ROOT / "site-v2" / "index.html").read_text(encoding="utf-8")

    assert 'class="module-nav"' in html
    for view in ["overview", "long", "short", "early", "trajectory", "trend", "momentum", "search"]:
        assert f'data-view-target="{view}"' in html
        assert f'data-view="{view}"' in html

    assert 'id="monthlyTrajectories"' in html
    assert 'id="earlyAssetSearch"' in html
    assert 'id="earlyResetSearch"' in html
    assert 'id="earlySearchStatus"' in html
    assert 'id="momentumScatter"' in html
    assert 'id="momentumAssetSearch"' in html
    assert 'id="momentumPositiveRank"' in html
    assert 'id="momentumNegativeRank"' in html
    assert 'id="momentumNewStates"' in html
    assert 'id="momentumTable"' in html
    assert html.index('data-view="trajectory"') < html.index('id="monthlyTrajectories"')


def test_publish_script_includes_original_root_and_v2_subdirectory():
    source = (PROJECT_ROOT / "scripts" / "publish_static_pages.py").read_text(encoding="utf-8")

    for expected in [
        '".nojekyll"',
        '"index.html"',
        '"data/app-data.json"',
        '"v2/index.html"',
        '"v2/app.js"',
        '"v2/styles.css"',
        '"v2/data/app-data.json"',
        '"site-v2"',
    ]:
        assert expected in source

    assert '"base_tree"' in source
    assert '"parents": [parent_sha]' in source
    assert '"force": False' in source


def test_v2_requirements_document_records_confirmed_scope():
    doc = (PROJECT_ROOT / "docs" / "v2需求拆解.md").read_text(encoding="utf-8")

    assert "## 已确认口径" in doc
    assert "bar = 一根 K 线" in doc
    assert "任意一个持续时间字段等于 1" in doc
    assert "5 / 10 / 20 / 60 / 250" in doc
    assert "30 自然日" in doc
    assert "商品" in doc
    assert "包含贵金属" in doc
    assert "观望" in doc
    assert "## 需要确认的问题" not in doc

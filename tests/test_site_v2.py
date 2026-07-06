import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"


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
        context.__elements[selector] = { innerHTML: "", dataset: {}, classList: { toggle: () => {} } };
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
  drawKline,
  priceHistory,
  toWeeklyBars,
  SEARCH_COLUMNS,
  MA_WINDOWS,
  DATA_URL,
};`,
  context
);

const api = context.__api;
assert.strictEqual(api.DATA_URL, "https://raw.githubusercontent.com/123xiaode456-boop/global-asset-tracker-dashboard/main/site-v2/data/app-data.json");
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
assert.strictEqual(JSON.stringify(relativePlot[1].map((trace) => trace.name)), JSON.stringify(["上涨", "下跌"]));
assert.strictEqual(JSON.stringify(relativePlot[1][0].x), JSON.stringify([3, -5]));
assert.strictEqual(JSON.stringify(relativePlot[1][0].y), JSON.stringify([2.5, -0.8]));
assert.strictEqual(JSON.stringify(relativePlot[1][1].x), JSON.stringify([-4, 6]));
assert.strictEqual(JSON.stringify(relativePlot[1][1].y), JSON.stringify([1.25, -1.7]));
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
        { asset_key: "CHEM1|Chem One", asset_code: "CHEM1", asset_name: "Chem One", relative_state: "lead", capital_state: "加杠杆", day_trend: up, day_trend_duration: 3, week_trend: up, week_trend_duration: 4, month_trend: up, month_trend_duration: 5 },
        { asset_key: "CHEM2|Chem Two", asset_code: "CHEM2", day_trend: down, day_trend_duration: 6, week_trend: down, week_trend_duration: 7, month_trend: down, month_trend_duration: 8 },
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
        points: [{ date: "2026-07-03", x: 1, y: 2 }],
      },
      {
        assetKey: "CHEM2|Chem Two",
        assetCode: "CHEM2",
        displayName: "化工二号",
        group: "化工品",
        points: [{ date: "2026-07-03", x: 2, y: 3 }],
      },
      {
        assetKey: "GOLD1|Gold",
        assetCode: "GOLD1",
        displayName: "黄金",
        group: "贵金属",
        points: [{ date: "2026-07-03", x: 4, y: 5 }],
      },
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
assert.ok(context.__elements["#longMatrix"].innerHTML.includes(">UNMAPPED_LONG<"));
assert.ok(context.__elements["#shortMatrix"].innerHTML.includes(">UNMAPPED_SHORT<"));
assert.ok(!context.__elements["#longMatrix"].innerHTML.includes(">NO_SIGNAL<"));
assert.ok(!context.__elements["#shortMatrix"].innerHTML.includes(">NO_SIGNAL<"));
context.__plots = [];
api.renderMonthlyTrajectories();
assert.strictEqual(api.selectedQuadrantGroup(), "化工品");
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("quadrant-tabs"));
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("quadrant-grid"));
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("化工一号"));
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("化工二号"));
assert.ok(!context.__elements["#monthlyTrajectories"].innerHTML.includes("黄金"));
assert.strictEqual(context.__plots.length, 2);
assert.strictEqual(JSON.stringify(context.__plots.map((plot) => plot[0])), JSON.stringify(["quadrant-化工品-0", "quadrant-化工品-1"]));
api.selectQuadrantGroup("贵金属");
assert.strictEqual(api.selectedQuadrantGroup(), "贵金属");
assert.ok(context.__elements["#monthlyTrajectories"].innerHTML.includes("黄金"));
assert.ok(!context.__elements["#monthlyTrajectories"].innerHTML.includes("化工一号"));
context.__plots = [];
api.selectTrendGroup("化工品");
assert.strictEqual(api.selectedTrendGroup(), "化工品");
assert.ok(context.__elements["#trendBars"].innerHTML.includes("trend-tabs"));
assert.ok(context.__elements["#trendBars"].innerHTML.includes("trend-grid"));
assert.ok(context.__elements["#trendBars"].innerHTML.includes("化工一号"));
assert.ok(context.__elements["#trendBars"].innerHTML.includes("化工二号"));
assert.ok(!context.__elements["#trendBars"].innerHTML.includes("黄金"));
assert.strictEqual(context.__plots.length, 2);
assert.strictEqual(JSON.stringify(context.__plots.map((plot) => plot[0])), JSON.stringify(["trend-化工品-0", "trend-化工品-1"]));
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
    for view in ["overview", "long", "short", "early", "trajectory", "trend", "search"]:
        assert f'data-view-target="{view}"' in html
        assert f'data-view="{view}"' in html

    assert 'id="monthlyTrajectories"' in html
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

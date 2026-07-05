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
  __plots: [],
  __elements: {},
  Plotly: {
    newPlot: (...args) => {
      context.__plots.push(args);
    },
  },
  document: {
    querySelector: (selector) => {
      if (!context.__elements[selector]) {
        context.__elements[selector] = { innerHTML: "" };
      }
      return context.__elements[selector];
    },
  },
  requestAnimationFrame: (fn) => fn(),
};
context.globalThis = context;
vm.createContext(context);
vm.runInContext(
  source +
    `
globalThis.__api = {
  state,
  currentCommodityRows,
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
  selectedQuadrantGroup,
  selectQuadrantGroup,
  renderMonthlyTrajectories,
  drawKline,
  priceHistory,
  toWeeklyBars,
  SEARCH_COLUMNS,
  MA_WINDOWS,
};`,
  context
);

const api = context.__api;
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
assert.ok(relativePlot[2].shapes.length >= 6);

api.state.date = "2026-06-22";
api.state.data = {
  datesByType: {
    core: ["2026-05-20", "2026-05-23", "2026-06-01", "2026-06-22", "2026-07-03"],
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
assert.strictEqual(JSON.stringify(api.coreDatesInLast30Days("2026-06-22")), JSON.stringify(["2026-05-23", "2026-06-01", "2026-06-22"]));
assert.strictEqual(JSON.stringify(api.currentCommodityRows([
  { ...rows[1], asset_key: "A|Alpha" },
  { ...rows[2], asset_key: "C|Alpha" },
  { ...rows[2], asset_code: "C", asset_key: "C|Wrong" },
]).map((row) => row.asset_key)), JSON.stringify(["A|Alpha", "C|Alpha"]));
api.state.date = "2026-07-03";
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
        ".kline-summary",
        ".missing",
        ".kline-grid",
        ".kline-card",
        ".kline-chart",
        ".quadrant-tabs",
        ".quadrant-grid",
        ".quadrant-card",
        ".quadrant-chart",
    ]:
        assert selector in css


def test_publish_script_includes_original_root_and_v2_subdirectory():
    source = (PROJECT_ROOT / "scripts" / "publish_static_pages.py").read_text(encoding="utf-8")

    for expected in [
        '"index.html"',
        '"data/app-data.json"',
        '"v2/index.html"',
        '"v2/app.js"',
        '"v2/styles.css"',
        '"v2/data/app-data.json"',
        '"site-v2"',
    ]:
        assert expected in source


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

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
  Plotly: {
    newPlot: (...args) => {
      context.__plots.push(args);
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
  filterLong,
  filterShort,
  sortPreview,
  hasAnyBarOne,
  decisionLabel,
  monthCutoff,
  drawKline,
  priceHistory,
  toWeeklyBars,
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
assert.strictEqual(JSON.stringify(api.sortPreview(rows.slice(0, 3)).map((row) => row.asset_code)), JSON.stringify(["A", "C", "B"]));
assert.strictEqual(api.hasAnyBarOne({ ...base, day_trend_duration: 8, week_trend_duration: 1 }), true);
assert.strictEqual(api.decisionLabel(rows[0]), "可做多");
assert.strictEqual(api.decisionLabel(rows[3]), "可做空");
assert.strictEqual(api.decisionLabel(rows[4]), "观望");
assert.strictEqual(api.monthCutoff("2026-06-22"), "2026-05-22");

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
assert.strictEqual(JSON.stringify(traceNames), JSON.stringify(["K线", "MA5", "MA10", "MA60", "MA250"]));
assert.ok(api.toWeeklyBars(bars).length < bars.length);
"""
    subprocess.run([str(NODE), "-e", script, str(PROJECT_ROOT / "site-v2" / "app.js")], check=True)


def test_site_v2_styles_support_kline_and_missing_panels():
    css = (PROJECT_ROOT / "site-v2" / "styles.css").read_text(encoding="utf-8")

    for selector in [".kline-summary", ".missing", ".kline-grid", ".kline-card", ".kline-chart"]:
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
    assert "5 / 10 / 60 / 250" in doc
    assert "包含贵金属" in doc
    assert "观望" in doc
    assert "## 需要确认的问题" not in doc

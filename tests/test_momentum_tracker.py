import subprocess
from pathlib import Path

from test_site_v2 import NODE, PROJECT_ROOT


def test_momentum_tracker_four_fields_history_and_lazy_loading(tmp_path):
    script = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
let source = fs.readFileSync(process.argv.at(-1), 'utf8').replace(/\nmain\(\)\.catch\([\s\S]*?\);\s*$/, '\n');
const elements = {};
const plots = [];
const requests = [];
let failHistory = false;
const row = { dataset_type: 'core', asset_key: 'A|Alpha', asset_code: 'A', asset_name: 'Alpha', asset_name_cn: '甲', current_momentum_state: '正', momentum_value: 0.0000123456, current_momentum_state_duration: 1, current_momentum_state_return: 2.5 };
const domestic = { ...row, dataset_type: 'domestic_main', asset_name_cn: '乙', current_momentum_state: '负', momentum_value: -2, current_momentum_state_duration: 12, current_momentum_state_return: -3.25 };
const blank = { ...row, asset_key: 'NULL|Missing', asset_code: 'NULL', current_momentum_state: '', momentum_value: null, current_momentum_state_duration: null, current_momentum_state_return: null };
const context = {
  console, URL, requestAnimationFrame: (fn) => fn(),
  document: { body: { dataset: {} }, querySelectorAll: () => [], querySelector: (selector) => elements[selector] ||= { innerHTML: '', textContent: '', value: '', insertAdjacentHTML(position, html) { this.innerHTML += html; } } },
  Plotly: { newPlot: (...args) => plots.push(args), Plots: { resize() {} } },
  fetch: async (url) => {
    requests.push(url);
    const date = url.match(/(2026-\d\d-\d\d)/)[1];
    if (failHistory && date === '2026-08-12') return { ok: false, status: 503 };
    return { ok: true, json: async () => date === '2026-08-19' ? [domestic] : [row, domestic] };
  },
};
vm.createContext(context);
vm.runInContext(source + '\nglobalThis.api={state,trackingAssetId,trackingRows,filteredTrackingRows,trackingCell,trackingHistoryDates,trackingHistory,renderMomentumTracker,setTrackingFilter,selectTrackingAsset,loadTrackingHistory,ensureViewData,datesForCurrentDataset,refreshCurrentView,TRACKING_FIELDS};', context);
const api = context.api;
api.state.activeView = 'momentum-tracker';
api.state.date = '2026-08-28';
api.state.data = {
  generatedAt: 'fixed', momentumDates: ['2026-07-17','2026-08-12','2026-08-19','2026-08-28','2026-08-31'],
  datesByType: { core: ['2026-08-28'] },
  momentumByDate: { '2026-08-28': [row, domestic, blank, { ...row, dataset_type: 'betting' }] },
  files: { momentumByDate: Object.fromEntries(['2026-08-12','2026-08-19','2026-08-28'].map(date => [date, `momentum/${date}.json`])) },
};
(async () => {
  assert.strictEqual(api.TRACKING_FIELDS.length, 4);
  assert.strictEqual(api.trackingRows().length, 3); // ETF stays separate.
  assert.notStrictEqual(api.trackingAssetId(row), api.trackingAssetId(domestic));
  assert.strictEqual(api.trackingCell('current_momentum_state_return', row), '2.50%');
  assert.strictEqual(api.trackingCell('momentum_value', row), '0.0000123456');
  assert.strictEqual(api.trackingCell('momentum_value', blank), '—');
  assert.strictEqual(api.trackingCell('momentum_value', {momentum_value: 0}), '0');
  assert.ok(api.trackingCell('current_momentum_state', {current_momentum_state:'<script>'}).includes('&lt;script&gt;'));
  api.renderMomentumTracker();
  assert.strictEqual(requests.length, 0); // Rendering never downloads all history.
  assert.strictEqual(plots.length, 0);
  assert.ok(elements['#trackingTable'].innerHTML.includes('当前动能状态累积涨跌幅'));
  assert.ok(elements['#trackingTable'].innerHTML.includes('class="bar-one"'));
  api.setTrackingFilter('datasetType', 'domestic_main');
  assert.strictEqual(api.filteredTrackingRows().length, 1);
  assert.strictEqual(api.state.trackingAssetId, api.trackingAssetId(domestic));
  api.setTrackingFilter('datasetType', 'all');
  api.setTrackingFilter('momentumState', 'positive');
  assert.strictEqual(api.filteredTrackingRows().length, 1);
  api.setTrackingFilter('momentumState', 'all');
  api.setTrackingFilter('barOne', true);
  assert.strictEqual(api.filteredTrackingRows().length, 1);
  api.setTrackingFilter('barOne', false);
  api.setTrackingFilter('search', '不存在');
  assert.strictEqual(api.filteredTrackingRows().length, 0);
  assert.ok(elements['#trackingCurrent'].innerHTML === '');
  api.setTrackingFilter('search', '');
  api.selectTrackingAsset(api.trackingAssetId(row));
  assert.deepStrictEqual(Array.from(api.trackingHistoryDates()), ['2026-08-12','2026-08-19','2026-08-28']);
  assert.ok(api.datesForCurrentDataset().includes('2026-08-19'));
  await api.ensureViewData('momentum-tracker');
  assert.strictEqual(requests.length, 0); // Current data already cached, no futures/snapshot/price requests.
  failHistory = true;
  await api.loadTrackingHistory();
  assert.ok(elements['#trackingHistory'].innerHTML.includes('加载未完成'));
  assert.strictEqual(api.state.trackingHistoryDate, '');
  failHistory = false;
  await api.loadTrackingHistory();
  assert.strictEqual(api.state.trackingHistoryDate, '2026-08-28');
  const history = api.trackingHistory();
  assert.strictEqual(history[1].row, null); // Same code in domestic must not fill a missing core row.
  const chart = plots.at(-1);
  assert.deepStrictEqual(Array.from(chart[1][0].y), [0.0000123456,null,0.0000123456]);
  assert.deepStrictEqual(Array.from(chart[1][2].y), [2.5,null,2.5]); // Source percentage, never multiply by 100.
  assert.strictEqual(chart[1][0].connectgaps, false);
  assert.ok(!chart[1][0].x.includes('2026-08-31'));
  api.selectTrackingAsset(api.trackingAssetId(domestic));
  assert.deepStrictEqual(Array.from(plots.at(-1)[1][0].y), [-2,-2,-2]);
  api.state.date = '2026-08-19';
  api.renderMomentumTracker();
  assert.ok(elements['#trackingHistory'].innerHTML.includes('点击'));
  assert.ok(requests.every(url => url.includes('/momentum/')));
  api.state.date = '2026-08-12';
  delete api.state.data.momentumByDate['2026-08-12'];
  failHistory = true;
  await api.refreshCurrentView();
  assert.ok(elements['#trackingTable'].innerHTML.includes('加载失败'));
  assert.strictEqual(elements['#trackingCurrent'].innerHTML, ''); // Never show stale-date values after a failed fetch.
  console.log('momentum tracker checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
    script_path = tmp_path / 'momentum-tracker-test.js'
    script_path.write_text(script, encoding='utf-8')
    subprocess.run([str(NODE), str(script_path), str(PROJECT_ROOT / 'site-v2/app.js')], check=True)


def test_momentum_tracker_panel_and_visibility_rules():
    html = (PROJECT_ROOT / 'site-v2/index.html').read_text(encoding='utf-8')
    css = (PROJECT_ROOT / 'site-v2/styles.css').read_text(encoding='utf-8')
    assert 'data-view-target="momentum-tracker"' in html
    assert 'data-view="momentum-tracker"' in html
    assert 'body[data-active-view="momentum-tracker"]' in css
    assert 'styles.css?v=20260830-momentum-tracker' in html
    for label in ('当前动能状态', '动能数值', '当前动能状态持续时间', '当前动能状态累积涨跌幅', '查看近30天历史'):
        assert label in html

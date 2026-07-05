from datetime import date
from pathlib import Path

from asset_tracker.dashboard_data import get_asset_panel_data, load_dashboard_snapshot, load_price_coverage
from asset_tracker.database import AssetDatabase
from asset_tracker.parsers import DatasetMetadata, ParsedDataset, parse_dataset_file

from conftest import CORE_PDF


def test_dashboard_snapshot_loads_latest_counts(tmp_path):
    parsed = parse_dataset_file(CORE_PDF)
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    db.import_parsed_dataset(parsed, CORE_PDF)

    snapshot = load_dashboard_snapshot(db.path)

    assert snapshot.latest_date == "2026-06-09"
    assert snapshot.dataset_types == ["core"]
    assert snapshot.asset_count == 235
    assert snapshot.latest_counts["total"] == 235
    assert snapshot.available_dates == ["2026-06-09"]


def test_dashboard_snapshot_can_load_selected_date(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_rows(
        db,
        "core",
        "day1-hash",
        date(2026, 6, 9),
        [_dashboard_observation("AAA", "Alpha", day_trend="上行趋势")],
    )
    _import_rows(
        db,
        "core",
        "day2-hash",
        date(2026, 6, 10),
        [_dashboard_observation("BBB", "Beta", day_trend="下行趋势")],
    )

    snapshot = load_dashboard_snapshot(db.path, dataset_date="2026-06-09")

    assert snapshot.latest_date == "2026-06-09"
    assert snapshot.available_dates == ["2026-06-09", "2026-06-10"]
    assert [row["asset_code"] for row in snapshot.latest_rows] == ["AAA"]
    assert snapshot.latest_counts["total"] == 1


def test_dashboard_snapshot_ranks_selected_date_opportunities(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_rows(
        db,
        "core",
        "opportunity-hash",
        date(2026, 6, 9),
        [
            _dashboard_observation(
                "AAA",
                "Alpha",
                day_trend="上行趋势",
                week_trend="上行趋势",
                month_trend="上行趋势",
                relative_state="lead",
                capital_state="加杠杆",
                relative_strength=112.0,
                strength_momentum=109.0,
                capital_daily_change=3.0,
                capital_value=88.0,
            ),
            _dashboard_observation(
                "BBB",
                "Beta",
                day_trend="上行趋势",
                week_trend="上行趋势",
                relative_state="Improving",
                capital_state="加杠杆",
                relative_strength=103.0,
                strength_momentum=102.0,
                capital_daily_change=0.5,
                capital_value=60.0,
            ),
            _dashboard_observation(
                "CCC",
                "Gamma",
                day_trend="下行趋势",
                week_trend="下行趋势",
                month_trend="下行趋势",
                relative_state="Lag",
                capital_state="去杠杆",
                relative_strength=88.0,
                strength_momentum=86.0,
                capital_daily_change=-2.5,
                capital_value=20.0,
            ),
            _dashboard_observation("DDD", "Delta", day_trend="无趋势"),
        ],
    )

    snapshot = load_dashboard_snapshot(db.path, dataset_date="2026-06-09")

    assert [row["asset_code"] for row in snapshot.long_opportunities] == ["AAA", "BBB"]
    assert snapshot.long_opportunities[0]["rank"] == 1
    assert snapshot.long_opportunities[0]["decision_label"] == "可做多"
    assert "周趋势上行" in snapshot.long_opportunities[0]["reasons"]
    assert [row["asset_code"] for row in snapshot.short_opportunities] == ["CCC"]
    assert snapshot.short_opportunities[0]["decision_label"] == "可做空"


def test_asset_panel_data_handles_missing_price_history(tmp_path):
    parsed = parse_dataset_file(CORE_PDF)
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    db.import_parsed_dataset(parsed, CORE_PDF)

    panel = get_asset_panel_data(db.path, "10Y1!")

    assert len(panel.signal_history) == 1
    assert panel.price_history == []
    assert panel.unmapped_price is True
    assert panel.latest_signal["asset_name"] == "10-Year Yield Futures"
    assert panel.trade_decision.label == "不做/观望"
    assert len(panel.quadrant_trajectory) == 1
    assert panel.quadrant_trajectory[0].quadrant == "Leading"


def test_asset_panel_data_uses_selected_date_for_decision_and_opportunity(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_rows(
        db,
        "core",
        "asset-day1-hash",
        date(2026, 6, 9),
        [
            _dashboard_observation(
                "AAA",
                "Alpha",
                day_trend="上行趋势",
                week_trend="上行趋势",
                relative_state="lead",
                capital_state="加杠杆",
            )
        ],
    )
    _import_rows(
        db,
        "core",
        "asset-day2-hash",
        date(2026, 6, 10),
        [
            _dashboard_observation(
                "AAA",
                "Alpha",
                day_trend="下行趋势",
                week_trend="下行趋势",
                relative_state="Lag",
                capital_state="去杠杆",
            )
        ],
    )

    panel = get_asset_panel_data(db.path, "AAA|Alpha", dataset_date="2026-06-09")

    assert panel.latest_signal["dataset_date"] == "2026-06-09"
    assert panel.trade_decision.label == "可做多"
    assert panel.opportunity["decision_label"] == "可做多"
    assert panel.opportunity["rank"] == 1
    assert [point.date for point in panel.quadrant_trajectory] == ["2026-06-09", "2026-06-10"]


def test_asset_panel_data_merges_indicator_history_for_similar_same_code_names(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_rows(
        db,
        "core",
        "similar-name-day1-hash",
        date(2026, 6, 9),
        [_dashboard_observation("EWA", "iShares MSCI Australia ETF", relative_strength=101.0)],
    )
    _import_rows(
        db,
        "core",
        "similar-name-day2-hash",
        date(2026, 6, 10),
        [_dashboard_observation("EWA", "iShares MSCI Australia Index Fund", relative_strength=105.0)],
    )

    panel = get_asset_panel_data(db.path, "EWA|iShares MSCI Australia Index Fund")

    assert [row["asset_name"] for row in panel.signal_history] == [
        "iShares MSCI Australia ETF",
        "iShares MSCI Australia Index Fund",
    ]
    assert [point.date for point in panel.quadrant_trajectory] == ["2026-06-09", "2026-06-10"]


def test_asset_panel_data_does_not_merge_indicator_history_for_different_same_code_assets(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_rows(
        db,
        "core",
        "different-name-day1-hash",
        date(2026, 6, 9),
        [_dashboard_observation("PL1!", "Platinum Futures", relative_strength=101.0)],
    )
    _import_rows(
        db,
        "core",
        "different-name-day2-hash",
        date(2026, 6, 10),
        [_dashboard_observation("PL1!", "Propylene Futures", relative_strength=105.0)],
    )

    panel = get_asset_panel_data(db.path, "PL1!|Propylene Futures")

    assert [row["asset_name"] for row in panel.signal_history] == ["Propylene Futures"]
    assert [point.date for point in panel.quadrant_trajectory] == ["2026-06-10"]


def test_price_coverage_counts_latest_unique_assets_with_price_history(tmp_path):
    parsed = parse_dataset_file(CORE_PDF)
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    db.import_parsed_dataset(parsed, CORE_PDF)
    first_asset = db.get_latest_observations()[0]
    db.upsert_price_bars(
        first_asset["asset_key"],
        [
            {
                "bar_date": "2026-06-09",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1000,
            }
        ],
        "manual",
    )

    coverage = load_price_coverage(db.path)

    assert coverage.latest_date == "2026-06-09"
    assert coverage.total_assets == 235
    assert coverage.assets_with_price == 1
    assert coverage.assets_without_price == 234
    assert round(coverage.coverage_ratio, 4) == round(1 / 235, 4)
    assert first_asset["asset_key"] not in {row["asset_key"] for row in coverage.missing_rows}
    assert coverage.missing_rows[0]["price_status"] == "缺行情"


def test_price_coverage_reuses_cached_price_for_same_asset_code_with_different_names(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_single_row(db, "core", "core-hash", "EWA", "iShares MSCI Australia Index Fund")
    _import_single_row(db, "betting", "betting-hash", "EWA", "iShares MSCI Australia ETF")
    db.upsert_price_bars(
        "EWA|iShares MSCI Australia ETF",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
        "manual",
    )

    coverage = load_price_coverage(db.path)

    assert coverage.total_assets == 2
    assert coverage.assets_with_price == 2
    assert coverage.assets_without_price == 0
    assert coverage.missing_rows == []


def test_asset_panel_data_reuses_price_history_for_same_asset_code_with_different_names(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    core_key = "EWA|iShares MSCI Australia Index Fund"
    _import_single_row(db, "core", "core-hash", "EWA", "iShares MSCI Australia Index Fund")
    _import_single_row(db, "betting", "betting-hash", "EWA", "iShares MSCI Australia ETF")
    db.upsert_price_bars(
        "EWA|iShares MSCI Australia ETF",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 23.5, "volume": 1}],
        "manual",
    )

    panel = get_asset_panel_data(db.path, core_key)

    assert panel.unmapped_price is False
    assert [row["close"] for row in panel.price_history] == [23.5]


def test_price_coverage_does_not_reuse_cached_price_for_different_assets_with_same_code(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_single_row(db, "core", "platinum-hash", "PL1!", "Platinum Futures")
    _import_single_row(db, "betting", "propylene-hash", "PL1!", "Propylene Futures")
    db.upsert_price_bars(
        "PL1!|Platinum Futures",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 10.0, "volume": 1}],
        "manual",
    )

    coverage = load_price_coverage(db.path)
    propylene_panel = get_asset_panel_data(db.path, "PL1!|Propylene Futures")

    assert coverage.total_assets == 2
    assert coverage.assets_with_price == 1
    assert coverage.assets_without_price == 1
    assert {row["asset_key"] for row in coverage.missing_rows} == {"PL1!|Propylene Futures"}
    assert propylene_panel.unmapped_price is True
    assert propylene_panel.price_history == []


def test_price_coverage_includes_latest_fetch_failure_reason(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_single_row(db, "core", "failure-log-hash", "UNMAPPED1!", "Unmapped Futures")
    db.record_price_fetch_log(
        asset_key="UNMAPPED1!|Unmapped Futures",
        asset_code="UNMAPPED1!",
        asset_name="Unmapped Futures",
        dataset_date="2026-06-09",
        market_symbol=None,
        status="skipped",
        message="no_free_source_candidate",
        start_date=None,
        end_date=None,
    )

    coverage = load_price_coverage(db.path)

    assert coverage.missing_rows[0]["last_fetch_status"] == "skipped"
    assert coverage.missing_rows[0]["last_fetch_message"] == "no_free_source_candidate"
    assert coverage.missing_rows[0]["last_fetch_symbol"] == ""
    assert coverage.missing_rows[0]["last_fetch_at"]


def _import_single_row(
    db: AssetDatabase,
    dataset_type: str,
    source_hash: str,
    asset_code: str,
    asset_name: str,
) -> None:
    _import_rows(
        db,
        dataset_type,
        source_hash,
        date(2026, 6, 9),
        [_dashboard_observation(asset_code, asset_name)],
    )


def _import_rows(
    db: AssetDatabase,
    dataset_type: str,
    source_hash: str,
    dataset_date: date,
    rows: list[dict],
) -> None:
    parsed = ParsedDataset(
        metadata=DatasetMetadata(dataset_date, dataset_type),
        source_path=Path(f"{source_hash}.xlsx"),
        source_hash=source_hash,
        rows=rows,
    )
    db.import_parsed_dataset(parsed, parsed.source_path)


def _dashboard_observation(
    asset_code: str,
    asset_name: str,
    day_trend: str = "上行趋势",
    week_trend: str = "上行趋势",
    month_trend: str = "上行趋势",
    relative_state: str = "lead",
    capital_state: str = "加杠杆",
    relative_strength: float = 105.0,
    strength_momentum: float = 103.0,
    capital_daily_change: float = 2.0,
    capital_value: float = 80.0,
) -> dict:
    return {
        "asset_code": asset_code,
        "asset_name": asset_name,
        "day_trend": day_trend,
        "day_trend_duration": 1,
        "week_trend": week_trend,
        "week_trend_duration": 1,
        "month_trend": month_trend,
        "month_trend_duration": 1,
        "close_position_60d": 0.7,
        "relative_strength": relative_strength,
        "strength_momentum": strength_momentum,
        "early_turn": 104.0,
        "relative_state_duration": 1,
        "relative_state": relative_state,
        "relative_state_return": 1.0,
        "previous_relative_state": "Improving",
        "previous_relative_state_return": 0.5,
        "previous_relative_state_duration": 2,
        "capital_state_duration": 1,
        "capital_state": capital_state,
        "capital_state_return": 1.0,
        "previous_capital_state": "去杠杆",
        "previous_capital_state_return": -0.5,
        "capital_value": capital_value,
        "capital_daily_change": capital_daily_change,
    }

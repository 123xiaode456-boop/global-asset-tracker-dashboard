import json
from datetime import date
from pathlib import Path

from asset_tracker.database import AssetDatabase
from asset_tracker.parsers import DatasetMetadata, ParsedDataset
from export_static_site import build_static_payload, export_static_shards


def test_static_export_includes_price_history_by_asset_key(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.xlsx"),
        source_hash="static-export-hash",
        rows=[
            {
                "asset_code": "AAA",
                "asset_name": "Alpha ETF",
                "day_trend": "上行趋势",
                "day_trend_duration": 2,
                "week_trend": "上行趋势",
                "week_trend_duration": 3,
                "month_trend": "上行趋势",
                "month_trend_duration": 4,
                "close_position_60d": 0.7,
                "relative_strength": 105.0,
                "strength_momentum": 103.0,
                "early_turn": 104.0,
                "relative_state_duration": 5,
                "relative_state": "lead",
                "relative_state_return": 1.0,
                "previous_relative_state": "Improving",
                "previous_relative_state_return": 0.5,
                "previous_relative_state_duration": 2,
                "capital_state_duration": 6,
                "capital_state": "加杠杆",
                "capital_state_return": 1.0,
                "previous_capital_state": "去杠杆",
                "previous_capital_state_return": -0.5,
                "capital_value": 80.0,
                "capital_daily_change": 2.0,
            }
        ],
    )
    db.import_parsed_dataset(parsed, parsed.source_path)
    db.upsert_price_bars(
        "AAA|Alpha ETF",
        [{"bar_date": "2026-06-09", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 1000}],
        "manual",
    )

    payload = build_static_payload(db.path)

    assert payload["priceHistories"]["AAA|Alpha ETF"][0]["close"] == 10.5
    assert payload["priceCoverage"]["AAA|Alpha ETF"]["hasPrice"] is True


def test_static_export_can_build_core_payload_with_full_signal_rows_and_commodity_price_scope(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 3), "core"),
        source_path=Path("sample.xlsx"),
        source_hash="commodity-only-export-hash",
        rows=[
            _sample_row("GC1!", "Gold Futures"),
            _sample_row("SPY", "SPDR S&P 500 ETF Trust"),
        ],
    )
    db.import_parsed_dataset(parsed, parsed.source_path)
    db.upsert_price_bars(
        "SPY|SPDR S&P 500 ETF Trust",
        [{"bar_date": "2026-07-03", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}],
        "manual",
    )

    payload = build_static_payload(db.path, commodity_only=True)
    snapshot = payload["snapshots"]["core|2026-07-03"]

    assert payload["datasetTypes"] == ["core"]
    assert set(payload["datesByType"]) == {"core"}
    assert [row["asset_code"] for row in snapshot["latestRows"]] == ["GC1!", "SPY"]
    assert "SPY|SPDR S&P 500 ETF Trust" not in payload["priceHistories"]


def test_static_export_marks_domestic_futures_in_futures_by_date(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 3), "core"),
        source_path=Path("sample.xlsx"),
        source_hash="domestic-futures-export-hash",
        rows=[
            _sample_row("TA1!", "PTA Futures", "PTA\u671f\u8d27"),
            _sample_row("RB1!", "RBOB Gasoline Futures", "RBOB汽油期货"),
        ],
    )
    db.import_parsed_dataset(parsed, parsed.source_path)

    payload = build_static_payload(db.path, commodity_only=True)
    items = payload["futuresByDate"]["2026-07-03"]

    assert {item["assetCode"]: item["isDomestic"] for item in items} == {
        "TA1!": True,
        "RB1!": False,
    }


def test_commodity_site_export_includes_betting_dates_rows_and_inline_momentum(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    core = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 8, 3), "core"),
        source_path=Path("core.xlsx"),
        source_hash="core-etf-site-export",
        rows=[_sample_row("GC1!", "Gold Futures")],
    )
    betting_row = {
        **_sample_row("159611", "电力ETF"),
        "current_momentum_state_duration": 1,
        "current_momentum_state": "正",
        "current_momentum_state_return": 2.5,
        "previous_momentum_state": "打点",
        "previous_momentum_state_return": 0.2,
        "momentum_value": 1.25,
        "momentum_daily_change": 0.35,
    }
    betting = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 8, 3), "betting"),
        source_path=Path("betting.xlsx"),
        source_hash="betting-etf-site-export",
        rows=[betting_row],
    )
    db.import_parsed_dataset(core, core.source_path)
    db.import_parsed_dataset(betting, betting.source_path)

    payload = build_static_payload(db.path, commodity_only=True)
    snapshot = payload["snapshots"]["betting|2026-08-03"]

    assert payload["datasetTypes"] == ["core", "betting"]
    assert payload["datesByType"]["betting"] == ["2026-08-03"]
    assert len(snapshot["latestRows"]) == 1
    assert snapshot["latestRows"][0]["asset_code"] == "159611"
    assert snapshot["latestRows"][0]["current_momentum_state"] == "正"
    assert snapshot["latestRows"][0]["momentum_value"] == 1.25
    assert "159611|电力ETF" in payload["priceCoverage"]


def test_static_export_merges_domestic_main_and_exports_momentum(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    core = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 17), "core"),
        source_path=Path("core.xlsx"),
        source_hash="core-2026-07-17",
        rows=[_sample_row("GC1!", "Gold Futures", "黄金期货")],
    )
    domestic = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 17), "domestic_main"),
        source_path=Path("domestic-main.xlsx"),
        source_hash="domestic-main-2026-07-17",
        rows=[_sample_row("AL8", "豆一主连", "豆一主连")],
    )
    momentum = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 17), "momentum"),
        source_path=Path("momentum.xlsx"),
        source_hash="momentum-2026-07-17",
        rows=[
            {
                "asset_code": "GC1!",
                "asset_name": "Gold Futures",
                "current_momentum_state_duration": 1,
                "current_momentum_state": "正动能",
                "current_momentum_state_return": 2.5,
                "previous_momentum_state": "打点",
                "previous_momentum_state_return": 0.2,
                "momentum_value": 1.25,
                "momentum_daily_change": 0.35,
            }
        ],
    )

    db.import_parsed_dataset(core, core.source_path)
    db.import_parsed_dataset(domestic, domestic.source_path)
    db.import_parsed_dataset(momentum, momentum.source_path)

    payload = build_static_payload(db.path, commodity_only=True)
    snapshot = payload["snapshots"]["core|2026-07-17"]

    assert [row["asset_code"] for row in snapshot["latestRows"]] == ["GC1!", "AL8"]
    assert payload["momentumDates"] == ["2026-07-17"]
    assert payload["momentumByDate"]["2026-07-17"][0]["current_momentum_state"] == "正动能"
    assert payload["momentumHistoryByAsset"]["GC1!|Gold Futures"][0]["momentum_value"] == 1.25
    domestic_item = next(item for item in payload["futuresByDate"]["2026-07-17"] if item["assetCode"] == "AL8")
    assert domestic_item["group"] == "农产品"
    assert domestic_item["isDomestic"] is True


def test_static_export_preserves_domestic_only_dates_for_trend_charts(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    core = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 8, 11), "core"),
        source_path=Path("core.xlsx"),
        source_hash="core-2026-08-11",
        rows=[_sample_row("GC1!", "Gold Futures", "黄金期货")],
    )
    domestic = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 8, 12), "domestic_main"),
        source_path=Path("domestic-main.xlsx"),
        source_hash="domestic-main-2026-08-12",
        rows=[_sample_row("EGL8", "乙二醇主连", "乙二醇主连")],
    )
    db.import_parsed_dataset(core, core.source_path)
    db.import_parsed_dataset(domestic, domestic.source_path)

    payload = build_static_payload(db.path, commodity_only=True)

    assert payload["datesByType"]["core"] == ["2026-08-11"]
    assert payload["commodityDates"] == ["2026-08-11", "2026-08-12"]
    assert [row["asset_code"] for row in payload["snapshots"]["core|2026-08-12"]["latestRows"]] == ["EGL8"]
    assert any(item["assetCode"] == "EGL8" for item in payload["futuresByDate"]["2026-08-12"])


def test_static_export_writes_lazy_shards_without_losing_source_rows(tmp_path):
    payload = {
        "generatedAt": "2026-08-27T21:15:47",
        "datasetTypes": ["core", "betting"],
        "datesByType": {"core": ["2026-08-27"], "betting": ["2026-08-19"]},
        "commodityDates": ["2026-08-27"],
        "snapshots": {
            "core|2026-08-27": {
                "latestDate": "2026-08-27",
                "availableDates": ["2026-08-27"],
                "datasetTypes": ["core"],
                "assetCount": 1,
                "latestCounts": {"total": 1},
                "latestRows": [{"asset_key": "GC1!|Gold Futures", "asset_code": "GC1!"}],
                "focusWatch": [{"asset_code": "GC1!"}],
                "riskWatch": [],
                "longOpportunities": [{"asset_code": "GC1!"}],
                "shortOpportunities": [],
            }
        },
        "futuresByDate": {"2026-08-27": [{"assetKey": "GC1!|Gold Futures", "points": []}]},
        "momentumDates": ["2026-08-27"],
        "momentumByDate": {"2026-08-27": [{"asset_key": "GC1!|Gold Futures", "momentum_value": 1.25}]},
        "momentumHistoryByAsset": {"GC1!|Gold Futures": [{"asset_key": "GC1!|Gold Futures", "momentum_value": 1.25}]},
        "priceHistories": {"GC1!|Gold Futures": [{"bar_date": "2026-08-27", "close": 100.0}]},
        "priceCoverage": {"GC1!|Gold Futures": {"hasPrice": True, "priceRows": 1}},
    }

    manifest_path = export_static_shards(payload, tmp_path / "data")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = manifest_path.parent / manifest["files"]["snapshots"]["core|2026-08-27"]
    momentum_path = manifest_path.parent / manifest["files"]["momentumByDate"]["2026-08-27"]

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    momentum = json.loads(momentum_path.read_text(encoding="utf-8"))
    assert snapshot["latestRows"] == payload["snapshots"]["core|2026-08-27"]["latestRows"]
    assert momentum == payload["momentumByDate"]["2026-08-27"]
    assert manifest["retainedData"]["momentumRowCount"] == 1
    assert manifest["commodityDates"] == ["2026-08-27"]
    assert not (manifest_path.parent / "momentum-history-by-asset.json").exists()


def _sample_row(asset_code: str, asset_name: str, asset_name_cn: str = "") -> dict:
    return {
        "asset_code": asset_code,
        "asset_name": asset_name,
        "asset_name_cn": asset_name_cn,
        "day_trend": "上行趋势",
        "day_trend_duration": 2,
        "week_trend": "上行趋势",
        "week_trend_duration": 3,
        "month_trend": "上行趋势",
        "month_trend_duration": 4,
        "close_position_60d": 0.7,
        "relative_strength": 105.0,
        "strength_momentum": 103.0,
        "early_turn": 104.0,
        "relative_state_duration": 5,
        "relative_state": "lead",
        "relative_state_return": 1.0,
        "previous_relative_state": "Improving",
        "previous_relative_state_return": 0.5,
        "previous_relative_state_duration": 2,
        "capital_state_duration": 6,
        "capital_state": "加杠杆",
        "capital_state_return": 1.0,
        "previous_capital_state": "去杠杆",
        "previous_capital_state_return": -0.5,
        "capital_value": 80.0,
        "capital_daily_change": 2.0,
    }

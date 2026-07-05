from datetime import date
from pathlib import Path

from asset_tracker.database import AssetDatabase
from asset_tracker.parsers import DatasetMetadata, ParsedDataset
from export_static_site import build_static_payload


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


def _sample_row(asset_code: str, asset_name: str) -> dict:
    return {
        "asset_code": asset_code,
        "asset_name": asset_name,
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

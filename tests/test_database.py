from asset_tracker.database import AssetDatabase
from asset_tracker.parsers import DatasetMetadata, ParsedDataset
from asset_tracker.parsers import parse_dataset_file
from datetime import date
from pathlib import Path

from conftest import CORE_PDF


def test_importing_same_file_twice_is_idempotent(tmp_path):
    parsed = parse_dataset_file(CORE_PDF)
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()

    first = db.import_parsed_dataset(parsed, CORE_PDF)
    second = db.import_parsed_dataset(parsed, CORE_PDF)

    assert first.inserted_rows == 235
    assert first.duplicate is False
    assert second.inserted_rows == 0
    assert second.duplicate is True
    assert db.count_observations() == 235
    assert db.count_assets() == 235

    logs = db.list_import_logs()
    assert len(logs) == 1
    assert logs[0]["file_hash"] == parsed.source_hash
    assert logs[0]["row_count"] == 235


def test_latest_rows_and_asset_history_are_queryable(tmp_path):
    parsed = parse_dataset_file(CORE_PDF)
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    db.import_parsed_dataset(parsed, CORE_PDF)

    latest = db.get_latest_observations("core")
    history = db.get_asset_history("10Y1!")

    assert len(latest) == 235
    assert latest[0]["dataset_date"] == "2026-06-09"
    assert len(history) == 1
    assert history[0]["asset_name"] == "10-Year Yield Futures"
    assert history[0]["relative_strength"] == 106.0


def test_symbol_mapping_can_be_saved_and_loaded(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()

    db.upsert_symbol_mapping(
        asset_code="SPY",
        asset_name="SPDR S&P 500 ETF Trust",
        market_symbol="SPY",
        price_source="yfinance",
        status="mapped",
        note="manual",
    )

    mapping = db.get_symbol_mapping("SPY")
    assert mapping["market_symbol"] == "SPY"
    assert mapping["price_source"] == "yfinance"
    assert db.list_symbol_mappings()[0]["asset_code"] == "SPY"


def test_import_stores_translated_asset_name(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.xlsx"),
        source_hash="translated-asset-hash",
        rows=[
            {
                "asset_code": "GC1!",
                "asset_name": "Gold Futures",
                "day_trend": "上行趋势",
                "day_trend_duration": 1,
                "week_trend": "上行趋势",
                "week_trend_duration": 1,
                "month_trend": "上行趋势",
                "month_trend_duration": 1,
                "close_position_60d": 0.7,
                "relative_strength": 105.0,
                "strength_momentum": 103.0,
                "early_turn": 104.0,
                "relative_state_duration": 1,
                "relative_state": "lead",
                "relative_state_return": 1.0,
                "previous_relative_state": "Improving",
                "previous_relative_state_return": 0.5,
                "previous_relative_state_duration": 2,
                "capital_state_duration": 1,
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

    row = db.get_latest_observations("core")[0]
    assert row["asset_name_cn"] == "黄金期货"
    assert row["asset_name_translation_status"] == "mapped"
    assert db.list_untranslated_asset_names() == []


def test_untranslated_asset_names_are_queryable(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.xlsx"),
        source_hash="untranslated-asset-hash",
        rows=[
            {
                "asset_code": "ZZZ",
                "asset_name": "Obscure Abbreviation",
                "day_trend": "无趋势",
                "day_trend_duration": 1,
                "week_trend": "无趋势",
                "week_trend_duration": 1,
                "month_trend": "无趋势",
                "month_trend_duration": 1,
                "close_position_60d": 0.5,
                "relative_strength": 100.0,
                "strength_momentum": 100.0,
                "early_turn": 100.0,
                "relative_state_duration": 1,
                "relative_state": "Weakening",
                "relative_state_return": 0.0,
                "previous_relative_state": "lead",
                "previous_relative_state_return": 0.0,
                "previous_relative_state_duration": 2,
                "capital_state_duration": 1,
                "capital_state": "无杠杆",
                "capital_state_return": 0.0,
                "previous_capital_state": "无杠杆",
                "previous_capital_state_return": 0.0,
                "capital_value": 50.0,
                "capital_daily_change": 0.0,
            }
        ],
    )

    db.import_parsed_dataset(parsed, parsed.source_path)

    missing = db.list_untranslated_asset_names()
    assert missing == [
        {
            "asset_key": "ZZZ|Obscure Abbreviation",
            "asset_code": "ZZZ",
            "asset_name": "Obscure Abbreviation",
            "asset_name_cn": "",
            "asset_name_translation_status": "unmapped",
        }
    ]


def test_momentum_dataset_is_stored_separately_and_idempotently(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 17), "momentum"),
        source_path=Path("momentum.xlsx"),
        source_hash="momentum-hash",
        rows=[
            {
                "asset_code": "SPY",
                "asset_name": "SPDR S&P 500 ETF Trust",
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

    first = db.import_parsed_dataset(parsed, parsed.source_path)
    second = db.import_parsed_dataset(parsed, parsed.source_path)

    assert first.inserted_rows == 1
    assert second.duplicate is True
    assert db.list_momentum_dates() == ["2026-07-17"]
    row = db.get_momentum_for_date("2026-07-17")[0]
    assert row["asset_code"] == "SPY"
    assert row["current_momentum_state"] == "正动能"
    assert row["momentum_value"] == 1.25
    assert db.get_momentum_history()[0]["dataset_date"] == "2026-07-17"


def test_core_dataset_with_inline_momentum_populates_both_observation_tables(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    row = {
        "asset_code": "SPY",
        "asset_name": "SPDR S&P 500 ETF Trust",
        "day_trend": "上行趋势",
        "day_trend_duration": 1,
        "week_trend": "上行趋势",
        "week_trend_duration": 2,
        "month_trend": "上行趋势",
        "month_trend_duration": 3,
        "close_position_60d": 0.75,
        "relative_strength": 105.5,
        "strength_momentum": 103.2,
        "early_turn": None,
        "relative_state_duration": 2,
        "relative_state": "lead",
        "relative_state_return": 2.4,
        "previous_relative_state": "Improving",
        "previous_relative_state_return": 1.2,
        "previous_relative_state_duration": 5,
        "capital_state_duration": 1,
        "capital_state": "加杠杆",
        "capital_state_return": 1.5,
        "previous_capital_state": "去杠杆",
        "previous_capital_state_return": -0.8,
        "capital_value": 88.2,
        "capital_daily_change": 2.1,
        "current_momentum_state_duration": 1,
        "current_momentum_state": "正",
        "current_momentum_state_return": 2.5,
        "previous_momentum_state": "打点",
        "previous_momentum_state_return": 0.2,
        "momentum_value": 1.25,
        "momentum_daily_change": 0.35,
    }
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 7, 20), "core"),
        source_path=Path("combined-core.xlsx"),
        source_hash="combined-core-hash",
        rows=[row],
    )

    db.import_parsed_dataset(parsed, parsed.source_path)

    assert db.get_observations_for_date("2026-07-20", "core")[0]["early_turn"] is None
    momentum = db.get_momentum_for_date("2026-07-20")[0]
    assert momentum["current_momentum_state"] == "正"
    assert momentum["momentum_value"] == 1.25

from datetime import date
from pathlib import Path

import asset_tracker.cli as cli
from asset_tracker.cli import run_fetch_prices, run_import, run_import_prices, run_map_symbol
from asset_tracker.database import AssetDatabase
from asset_tracker.parsers import DatasetMetadata, ParsedDataset, SOURCE_COLUMNS
from test_parser import _write_minimal_xlsx

from conftest import CORE_PDF


def test_run_import_writes_database_and_markdown_report(tmp_path):
    db_path = tmp_path / "signals.sqlite"
    report_dir = tmp_path / "reports"

    results = run_import([CORE_PDF], db_path=db_path, report_dir=report_dir)

    assert len(results) == 1
    assert results[0].inserted_rows == 235
    assert AssetDatabase(db_path).count_observations() == 235
    report = report_dir / "2026-06-09_core.md"
    assert report.exists()
    assert "重点观察" in report.read_text(encoding="utf-8")


def test_run_import_accepts_daily_excel_and_writes_report(tmp_path):
    workbook = tmp_path / "26-06-10 数据总表（趋势识别＋相对比价＋资金监控）（核心数据集）.xlsx"
    _write_minimal_xlsx(
        workbook,
        [
            SOURCE_COLUMNS,
            [
                "SPY",
                "SPDR S&P 500 ETF Trust",
                "上行趋势",
                1,
                "上行趋势",
                2,
                "上行趋势",
                3,
                0.75,
                105.5,
                103.2,
                101.1,
                1,
                "lead",
                2.4,
                "Improving",
                1.2,
                5,
                1,
                "加杠杆",
                1.5,
                "去杠杆",
                -0.8,
                88.2,
                2.1,
            ],
        ],
    )

    db_path = tmp_path / "signals.sqlite"
    report_dir = tmp_path / "reports"

    results = run_import([workbook], db_path=db_path, report_dir=report_dir)

    assert results[0].inserted_rows == 1
    assert AssetDatabase(db_path).get_latest_observations("core")[0]["asset_code"] == "SPY"
    report = report_dir / "2026-06-10_core.md"
    assert report.exists()
    assert "SPY" in report.read_text(encoding="utf-8")


def test_run_import_archive_raw_reuses_existing_readonly_file(tmp_path, monkeypatch):
    workbook = tmp_path / "26-06-10 sample.xlsx"
    _write_minimal_xlsx(
        workbook,
        [
            SOURCE_COLUMNS,
            [
                "SPY",
                "SPDR S&P 500 ETF Trust",
                "up",
                1,
                "up",
                2,
                "up",
                3,
                0.75,
                105.5,
                103.2,
                101.1,
                1,
                "Lead",
                2.4,
                "Improving",
                1.2,
                5,
                1,
                "Leveraging",
                1.5,
                "Deleveraging",
                -0.8,
                88.2,
                2.1,
            ],
        ],
    )
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "signals.sqlite"
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(cli, "DEFAULT_RAW_DIR", raw_dir)

    first = run_import([workbook], db_path=db_path, report_dir=report_dir, archive_raw=True)
    archived = raw_dir / "2026-06-10" / workbook.name
    archived.chmod(0o444)
    try:
        second = run_import([workbook], db_path=db_path, report_dir=report_dir, archive_raw=True)
    finally:
        archived.chmod(0o666)

    assert first[0].inserted_rows == 1
    assert archived.exists()
    assert second[0].duplicate
    assert second[0].inserted_rows == 0


def test_run_fetch_prices_stores_bars_for_latest_observation(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("SPY", "SPDR S&P 500 ETF Trust")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="sample-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))

    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append((row["asset_code"], market_symbol, start, end))
        return [
            {
                "bar_date": "2026-06-09",
                "open": 99.0,
                "high": 101.0,
                "low": 98.0,
                "close": 100.0,
                "volume": 123456,
            }
        ]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(db_path=db_path, asset_identifier="SPY|SPDR S&P 500 ETF Trust")

    assert results[0].asset_identifier == "SPY|SPDR S&P 500 ETF Trust"
    assert results[0].market_symbol == "SPY"
    assert results[0].inserted_rows == 1
    assert calls == [("SPY", "SPY", None, None)]
    assert db.get_price_history("SPY|SPDR S&P 500 ETF Trust")[0]["close"] == 100.0


def test_run_import_prices_stores_manual_csv_for_latest_asset(tmp_path):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("159632", "Nasdaq ETF")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="manual-price-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    csv_path = tmp_path / "nasdaq_prices.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-06-08,10,11,9,10.5,1000\n"
        "2026-06-09,10.5,12,10,11.8,1200\n",
        encoding="utf-8",
    )

    result = run_import_prices(
        db_path=db_path,
        asset_identifier="159632|Nasdaq ETF",
        csv_path=csv_path,
        source="manual_csv",
    )

    history = db.get_price_history("159632|Nasdaq ETF")
    latest_logs = db.get_latest_price_fetch_logs(["159632|Nasdaq ETF"])
    assert result.status == "imported"
    assert result.inserted_rows == 2
    assert [row["close"] for row in history] == [10.5, 11.8]
    assert history[0]["source"] == "manual_csv"
    assert latest_logs["159632|Nasdaq ETF"]["status"] == "imported"
    assert latest_logs["159632|Nasdaq ETF"]["message"] == "manual_csv_rows=2"


def test_run_import_prices_accepts_chinese_csv_headers(tmp_path):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    csv_path = tmp_path / "prices_zh.csv"
    csv_path.write_text(
        "日期,开盘,最高,最低,收盘,成交量\n"
        "2026/06/09,20,21,19,20.5,3000\n",
        encoding="utf-8-sig",
    )

    result = run_import_prices(
        db_path=db_path,
        asset_identifier="MISSING|Manual Asset",
        csv_path=csv_path,
        source="manual_csv",
    )

    history = db.get_price_history("MISSING|Manual Asset")
    assert result.asset_identifier == "MISSING|Manual Asset"
    assert result.inserted_rows == 1
    assert history[0]["bar_date"] == "2026-06-09"
    assert history[0]["open"] == 20.0
    assert history[0]["close"] == 20.5


def test_run_map_symbol_overrides_fetch_price_symbol(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("CUSTOM1!", "Custom Futures")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="custom-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))

    mapped = run_map_symbol(
        db_path=db_path,
        asset_identifier="CUSTOM1!|Custom Futures",
        market_symbol="CUSTOM-FUT",
        price_source="yfinance",
        note="manual test",
    )
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append(market_symbol)
        return [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)
    results = run_fetch_prices(db_path=db_path, asset_identifier="CUSTOM1!|Custom Futures")

    assert mapped["market_symbol"] == "CUSTOM-FUT"
    assert calls == ["CUSTOM-FUT"]
    assert results[0].inserted_rows == 1


def test_run_fetch_prices_deduplicates_same_asset_key_across_datasets(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("EFA", "iShares MSCI EAFE ETF")
    for dataset_type, file_hash in [("core", "core-hash"), ("betting", "betting-hash")]:
        parsed = ParsedDataset(
            metadata=DatasetMetadata(date(2026, 6, 9), dataset_type),
            source_path=Path(f"{dataset_type}.pdf"),
            source_hash=file_hash,
            rows=[row],
        )
        db.import_parsed_dataset(parsed, Path(f"{dataset_type}.pdf"))

    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append(row["asset_key"])
        return [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(db_path=db_path)

    assert [result.asset_identifier for result in results] == ["EFA|iShares MSCI EAFE ETF"]
    assert calls == ["EFA|iShares MSCI EAFE ETF"]


def test_run_fetch_prices_records_latest_fetch_failure_reason(tmp_path):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("UNMAPPED1!", "Unmapped Futures")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="unmapped-fetch-log-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))

    results = run_fetch_prices(db_path=db_path, asset_identifier="UNMAPPED1!|Unmapped Futures")
    latest_logs = db.get_latest_price_fetch_logs(["UNMAPPED1!|Unmapped Futures"])

    assert results[0].status == "skipped"
    assert latest_logs["UNMAPPED1!|Unmapped Futures"]["status"] == "skipped"
    assert latest_logs["UNMAPPED1!|Unmapped Futures"]["message"] == "no_free_source_candidate"
    assert latest_logs["UNMAPPED1!|Unmapped Futures"]["market_symbol"] is None


def test_run_fetch_prices_records_source_exception_message(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("159919", "沪深300ETF")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="source-error-log-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))

    def fail_fetch_price_history(row, start=None, end=None, market_symbol=None):
        raise RuntimeError("akshare fund_etf_hist_em failed: proxy disconnected")

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fail_fetch_price_history)

    results = run_fetch_prices(db_path=db_path, asset_identifier="159919|沪深300ETF")
    latest_logs = db.get_latest_price_fetch_logs(["159919|沪深300ETF"])

    assert results[0].status == "error"
    assert "proxy disconnected" in results[0].message
    assert latest_logs["159919|沪深300ETF"]["status"] == "error"
    assert "proxy disconnected" in latest_logs["159919|沪深300ETF"]["message"]


def test_run_fetch_prices_tries_next_candidate_when_first_symbol_is_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("123456", "Dual Market Asset")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="dual-market-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append(market_symbol)
        if market_symbol == "123456.SS":
            return [{"bar_date": "2026-06-09", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}]
        return []

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(db_path=db_path, asset_identifier="123456|Dual Market Asset")

    assert calls == ["123456.SZ", "123456.SS"]
    assert results[0].market_symbol == "123456.SS"
    assert results[0].inserted_rows == 1
    assert db.get_price_history("123456|Dual Market Asset")[0]["close"] == 2


def test_run_fetch_prices_skips_asset_cached_through_latest_signal_date(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("SPY", "SPDR S&P 500 ETF Trust")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="cached-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    db.upsert_price_bars(
        "SPY|SPDR S&P 500 ETF Trust",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
        "manual",
    )

    def fail_fetch(*args, **kwargs):
        raise AssertionError("cached asset should not hit external source")

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fail_fetch)

    results = run_fetch_prices(db_path=db_path, asset_identifier="SPY|SPDR S&P 500 ETF Trust")

    assert results[0].status == "cached"
    assert results[0].market_symbol == "SPY"
    assert results[0].inserted_rows == 0
    assert results[0].message == "price_cached_through=2026-06-09"


def test_run_fetch_prices_skips_asset_cached_under_same_asset_code_with_different_name(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    for dataset_type, asset_name, file_hash in [
        ("core", "iShares MSCI Australia Index Fund", "same-code-core-hash"),
        ("betting", "iShares MSCI Australia ETF", "same-code-betting-hash"),
    ]:
        parsed = ParsedDataset(
            metadata=DatasetMetadata(date(2026, 6, 9), dataset_type),
            source_path=Path(f"{dataset_type}.pdf"),
            source_hash=file_hash,
            rows=[_sample_observation("EWA", asset_name)],
        )
        db.import_parsed_dataset(parsed, Path(f"{dataset_type}.pdf"))
    db.upsert_price_bars(
        "EWA|iShares MSCI Australia ETF",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
        "manual",
    )

    def fail_fetch(*args, **kwargs):
        raise AssertionError("same-code cached asset should not hit external source")

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fail_fetch)

    results = run_fetch_prices(
        db_path=db_path,
        asset_identifier="EWA|iShares MSCI Australia Index Fund",
    )

    assert results[0].status == "cached"
    assert results[0].market_symbol == "EWA"
    assert results[0].inserted_rows == 0
    assert results[0].message == "price_cached_through=2026-06-09"


def test_run_fetch_prices_does_not_skip_different_asset_cached_under_same_code(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    for dataset_type, asset_name, file_hash in [
        ("core", "Platinum Futures", "same-code-platinum-hash"),
        ("betting", "Propylene Futures", "same-code-propylene-hash"),
    ]:
        parsed = ParsedDataset(
            metadata=DatasetMetadata(date(2026, 6, 9), dataset_type),
            source_path=Path(f"{dataset_type}.pdf"),
            source_hash=file_hash,
            rows=[_sample_observation("PL1!", asset_name)],
        )
        db.import_parsed_dataset(parsed, Path(f"{dataset_type}.pdf"))
    db.upsert_price_bars(
        "PL1!|Platinum Futures",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
        "manual",
    )
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append(row["asset_key"])
        return [{"bar_date": "2026-06-09", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)
    monkeypatch.setattr("asset_tracker.cli.guess_symbol_candidates", lambda row: ["PL=F"])

    results = run_fetch_prices(
        db_path=db_path,
        asset_identifier="PL1!|Propylene Futures",
    )

    assert results[0].status == "fetched"
    assert results[0].inserted_rows == 1
    assert calls == ["PL1!|Propylene Futures"]
    assert db.get_price_history("PL1!|Propylene Futures")[0]["close"] == 2


def test_run_fetch_prices_force_refresh_ignores_latest_signal_cache(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    row = _sample_observation("SPY", "SPDR S&P 500 ETF Trust")
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="force-refresh-hash",
        rows=[row],
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    db.upsert_price_bars(
        "SPY|SPDR S&P 500 ETF Trust",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
        "manual",
    )
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append(market_symbol)
        return [{"bar_date": "2026-06-10", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(
        db_path=db_path,
        asset_identifier="SPY|SPDR S&P 500 ETF Trust",
        force_refresh=True,
    )

    assert calls == ["SPY"]
    assert results[0].status == "fetched"
    assert results[0].inserted_rows == 1


def test_run_fetch_prices_can_filter_to_us_like_assets(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    rows = [
        _sample_observation("159919", "沪深300ETF"),
        _sample_observation("SPY", "SPDR S&P 500 ETF Trust"),
        _sample_observation("ES1!", "E-mini S&P 500 Futures"),
    ]
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="asset-kind-hash",
        rows=rows,
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append((row["asset_code"], market_symbol))
        return [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(db_path=db_path, asset_kind="us-like", force_refresh=True)

    assert [result.asset_code for result in results] == ["SPY"]
    assert calls == [("SPY", "SPY")]


def test_run_fetch_prices_missing_only_filters_cached_assets_before_limit(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    rows = [
        _sample_observation("AAA", "Cached ETF"),
        _sample_observation("BBB", "Missing ETF"),
    ]
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="missing-only-hash",
        rows=rows,
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    db.upsert_price_bars(
        "AAA|Cached ETF",
        [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
        "manual",
    )
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append(row["asset_code"])
        return [{"bar_date": "2026-06-09", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(db_path=db_path, missing_only=True, limit=1)

    assert [result.asset_code for result in results] == ["BBB"]
    assert calls == ["BBB"]


def test_run_fetch_prices_can_filter_to_us_etf_assets(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.sqlite"
    db = AssetDatabase(db_path)
    db.initialize()
    rows = [
        _sample_observation("AUDUSD", "AUD/USD"),
        _sample_observation("BTCUSD", "Bitcoin / U.S. dollar"),
        _sample_observation("DE10Y", "Germany 10 Year Government Bonds Yield"),
        _sample_observation("HSTECH", "Hang Seng TECH Index"),
        _sample_observation("IVV", "iShares Core S&P 500 ETF"),
        _sample_observation("DBE", "Invesco DB Energy Fund"),
    ]
    parsed = ParsedDataset(
        metadata=DatasetMetadata(date(2026, 6, 9), "core"),
        source_path=Path("sample.pdf"),
        source_hash="us-etf-kind-hash",
        rows=rows,
    )
    db.import_parsed_dataset(parsed, Path("sample.pdf"))
    calls = []

    def fake_fetch_price_history(row, start=None, end=None, market_symbol=None):
        calls.append((row["asset_code"], market_symbol))
        return [{"bar_date": "2026-06-09", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    monkeypatch.setattr("asset_tracker.cli.fetch_price_history", fake_fetch_price_history)

    results = run_fetch_prices(db_path=db_path, asset_kind="us-etf", force_refresh=True)

    assert [result.asset_code for result in results] == ["DBE", "IVV"]
    assert calls == [("DBE", "DBE"), ("IVV", "IVV")]


def _sample_observation(asset_code: str, asset_name: str) -> dict:
    return {
        "asset_code": asset_code,
        "asset_name": asset_name,
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

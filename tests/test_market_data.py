import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from asset_tracker.market_data import build_symbol_mapping_queue, fetch_price_history, guess_symbol_candidates


def test_guess_symbol_candidates_handles_common_markets():
    assert guess_symbol_candidates({"asset_code": "SPY", "asset_name": "SPDR S&P 500 ETF Trust"})[0] == "SPY"
    assert "159919.SZ" in guess_symbol_candidates({"asset_code": "159919", "asset_name": "沪深300"})
    assert "600519.SS" in guess_symbol_candidates({"asset_code": "600519", "asset_name": "贵州茅台"})
    assert guess_symbol_candidates({"asset_code": "UNMAPPED1!", "asset_name": "Unmapped Futures"}) == []


def test_guess_symbol_candidates_handles_hk_counter_codes():
    candidates = guess_symbol_candidates(
        {
            "asset_code": "003067",
            "asset_name": "iShares Hang Seng TECH ETF HKD Counter",
        }
    )

    assert candidates[0] == "3067.HK"


def test_guess_symbol_candidates_handles_forex_pairs():
    assert guess_symbol_candidates({"asset_code": "AUDUSD", "asset_name": "AUD/USD"}) == ["AUDUSD=X"]
    assert guess_symbol_candidates({"asset_code": "AUDJPY", "asset_name": "AUD/JPY"}) == ["AUDJPY=X"]
    assert guess_symbol_candidates({"asset_code": "EUR/USD", "asset_name": "Euro / U.S. Dollar"}) == ["EURUSD=X"]


def test_guess_symbol_candidates_handles_common_continuous_futures():
    assert guess_symbol_candidates({"asset_code": "ES1!", "asset_name": "E-mini S&P 500 Futures"}) == ["ES=F"]
    assert guess_symbol_candidates({"asset_code": "GC1!", "asset_name": "Gold Futures"}) == ["GC=F"]
    assert guess_symbol_candidates({"asset_code": "CL1!", "asset_name": "Crude Oil Futures"}) == ["CL=F"]
    assert guess_symbol_candidates({"asset_code": "ZN1!", "asset_name": "10-Year T-Note Futures"}) == ["ZN=F"]


def test_unmapped_queue_keeps_assets_without_free_source_mapping():
    rows = [
        {"asset_code": "SPY", "asset_name": "SPDR S&P 500 ETF Trust"},
        {"asset_code": "ES1!", "asset_name": "E-mini S&P 500 Futures"},
        {"asset_code": "UNMAPPED1!", "asset_name": "Unmapped Futures"},
    ]

    queue = build_symbol_mapping_queue(rows, existing_map={"SPY": {"market_symbol": "SPY"}})

    assert queue == [
        {
            "asset_code": "UNMAPPED1!",
            "asset_name": "Unmapped Futures",
            "asset_name_cn": "",
            "reason": "no_free_source_candidate",
        }
    ]


def test_unmapped_queue_keeps_chinese_name_for_search():
    rows = [
        {"asset_code": "CUSTOM1!", "asset_name": "Custom Futures", "asset_name_cn": "自定义期货"},
    ]

    queue = build_symbol_mapping_queue(rows)

    assert queue == [
        {
            "asset_code": "CUSTOM1!",
            "asset_name": "Custom Futures",
            "asset_name_cn": "自定义期货",
            "reason": "no_free_source_candidate",
        }
    ]


def test_fetch_price_history_surfaces_akshare_daily_errors(monkeypatch):
    def fake_fund_etf_hist_em(symbol, period, start_date, end_date):
        raise RuntimeError("proxy disconnected")

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(fund_etf_hist_em=fake_fund_etf_hist_em))

    with pytest.raises(RuntimeError, match="akshare fund_etf_hist_em failed: proxy disconnected"):
        fetch_price_history(
            {"asset_code": "159919", "asset_name": "沪深300"},
            start="2026-06-01",
            end="2026-06-21",
            market_symbol="159919.SZ",
        )


def test_fetch_price_history_uses_akshare_for_hk_symbols(monkeypatch):
    calls = []

    def fake_stock_hk_hist(symbol, period, start_date, end_date, adjust):
        calls.append((symbol, period, start_date, end_date, adjust))
        return pd.DataFrame(
            [
                {
                    "日期": "2026-06-18",
                    "开盘": 100.0,
                    "最高": 103.0,
                    "最低": 99.0,
                    "收盘": 102.0,
                    "成交量": 123456,
                }
            ]
        )

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_hk_hist=fake_stock_hk_hist))
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        SimpleNamespace(download=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("yfinance should not be used"))),
    )

    rows = fetch_price_history(
        {"asset_code": "003067", "asset_name": "iShares Hang Seng TECH ETF HKD Counter"},
        start="2026-06-01",
        end="2026-06-21",
        market_symbol="3067.HK",
    )

    assert calls == [("03067", "daily", "20260601", "20260621", "")]
    assert rows == [
        {
            "bar_date": "2026-06-18",
            "open": 100.0,
            "high": 103.0,
            "low": 99.0,
            "close": 102.0,
            "volume": 123456.0,
        }
    ]


def test_fetch_price_history_falls_back_to_akshare_hk_daily(monkeypatch):
    calls = []

    def fake_stock_hk_hist(symbol, period, start_date, end_date, adjust):
        calls.append(("hist", symbol, start_date, end_date))
        raise RuntimeError("eastmoney unavailable")

    def fake_stock_hk_daily(symbol, adjust):
        calls.append(("daily", symbol, adjust))
        return pd.DataFrame(
            [
                {"date": "2026-05-29", "open": 95.0, "high": 96.0, "low": 94.0, "close": 95.5, "volume": 1},
                {"date": "2026-06-18", "open": 100.0, "high": 103.0, "low": 99.0, "close": 102.0, "volume": 123456},
            ]
        )

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(stock_hk_hist=fake_stock_hk_hist, stock_hk_daily=fake_stock_hk_daily),
    )
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        SimpleNamespace(download=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("yfinance should not be used"))),
    )

    rows = fetch_price_history(
        {"asset_code": "003067", "asset_name": "iShares Hang Seng TECH ETF HKD Counter"},
        start="2026-06-01",
        end="2026-06-21",
        market_symbol="3067.HK",
    )

    assert calls == [("hist", "03067", "20260601", "20260621"), ("daily", "03067", "")]
    assert rows == [
        {
            "bar_date": "2026-06-18",
            "open": 100.0,
            "high": 103.0,
            "low": 99.0,
            "close": 102.0,
            "volume": 123456.0,
        }
    ]

from __future__ import annotations

from datetime import date
from typing import Any

from .domestic_futures import domestic_futures_symbol


def guess_symbol_candidates(row: dict[str, Any]) -> list[str]:
    code = str(row.get("asset_code", "")).strip()
    asset_name = str(row.get("asset_name", "")).strip()
    if not code:
        return []
    forex_symbol = _forex_symbol(code, asset_name)
    if forex_symbol:
        return [forex_symbol]
    domestic_symbol = domestic_futures_symbol(row)
    if domestic_symbol:
        return [domestic_symbol]
    if "!" in code:
        futures_symbol = _continuous_futures_symbol(code)
        return [futures_symbol] if futures_symbol else []
    if code.startswith("^"):
        return [code]
    if "." in code:
        return [code]
    if _looks_like_hk_counter(code, asset_name):
        return [f"{int(code):04d}.HK"]
    if code.isdigit() and len(code) == 6:
        if code.startswith(("15", "16", "18", "00", "30")):
            return [f"{code}.SZ"]
        if code.startswith(("50", "51", "52", "56", "58", "60", "68", "90")):
            return [f"{code}.SS"]
        return [f"{code}.SZ", f"{code}.SS"]
    if code.replace("-", "").isalnum() and len(code) <= 8:
        return [code]
    return []


def build_symbol_mapping_queue(
    rows: list[dict[str, Any]],
    existing_map: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    mapped = existing_map or {}
    queue = []
    seen: set[str] = set()
    for row in rows:
        asset_code = str(row.get("asset_code", "")).strip()
        if not asset_code or asset_code in seen:
            continue
        seen.add(asset_code)
        existing = mapped.get(asset_code)
        if existing and existing.get("market_symbol"):
            continue
        if not guess_symbol_candidates(row):
            queue.append(
                {
                    "asset_code": asset_code,
                    "asset_name": str(row.get("asset_name", "")).strip(),
                    "asset_name_cn": str(row.get("asset_name_cn", "")).strip(),
                    "reason": "no_free_source_candidate",
                }
            )
    return queue


def fetch_price_history(
    row: dict[str, Any],
    start: date | str | None = None,
    end: date | str | None = None,
    market_symbol: str | None = None,
) -> list[dict[str, Any]]:
    symbol = market_symbol or (guess_symbol_candidates(row)[0] if guess_symbol_candidates(row) else None)
    if not symbol:
        return []
    if symbol.endswith(".CNFUT"):
        return _fetch_akshare_cn_futures_daily(symbol, start, end)
    if symbol.endswith((".SZ", ".SS")):
        return _fetch_akshare_daily(symbol, start, end)
    if symbol.endswith(".HK"):
        rows = _fetch_akshare_hk_daily(symbol, start, end)
        if rows:
            return rows
    if _looks_like_us_symbol(symbol):
        rows = _fetch_akshare_us_daily(symbol, start, end)
        if rows:
            return rows
    rows = _fetch_yfinance_daily(symbol, start, end)
    if rows:
        return rows
    return _fetch_akshare_us_daily(symbol, start, end)


def _fetch_yfinance_daily(
    symbol: str,
    start: date | str | None,
    end: date | str | None,
) -> list[dict[str, Any]]:
    try:
        import yfinance as yf
    except ImportError:
        return []
    frame = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=False)
    if frame.empty:
        return []
    rows = []
    for index, row in frame.reset_index().iterrows():
        bar_date = row.get("Date")
        rows.append(
            {
                "bar_date": bar_date.date().isoformat() if hasattr(bar_date, "date") else str(bar_date)[:10],
                "open": _maybe_float(row.get("Open")),
                "high": _maybe_float(row.get("High")),
                "low": _maybe_float(row.get("Low")),
                "close": _maybe_float(row.get("Close")),
                "volume": _maybe_float(row.get("Volume")),
            }
        )
    return rows


def _fetch_akshare_daily(
    symbol: str,
    start: date | str | None,
    end: date | str | None,
) -> list[dict[str, Any]]:
    try:
        import akshare as ak
    except ImportError:
        return []
    code = symbol.split(".", 1)[0]
    start_date = _ak_date(start)
    end_date = _ak_date(end)
    try:
        frame = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise RuntimeError(f"akshare fund_etf_hist_em failed: {exc}") from exc
    if frame.empty:
        return []
    return _daily_rows_from_frame(frame, start=start, end=end)


def _fetch_akshare_hk_daily(
    symbol: str,
    start: date | str | None,
    end: date | str | None,
) -> list[dict[str, Any]]:
    try:
        import akshare as ak
    except ImportError:
        return []
    code = _hk_symbol_for_akshare(symbol)
    start_date = _ak_date(start)
    end_date = _ak_date(end)
    try:
        frame = ak.stock_hk_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
    except Exception:
        frame = None
    if frame is not None and not frame.empty:
        rows = _daily_rows_from_frame(frame, start=start, end=end)
        if rows:
            return rows
    try:
        frame = ak.stock_hk_daily(symbol=code, adjust="")
    except Exception:
        return []
    if frame.empty:
        return []
    return _daily_rows_from_frame(frame, start=start, end=end)


def _fetch_akshare_us_daily(
    symbol: str,
    start: date | str | None,
    end: date | str | None,
) -> list[dict[str, Any]]:
    if symbol.startswith("^") or "/" in symbol:
        return []
    try:
        import akshare as ak
    except ImportError:
        return []
    try:
        frame = ak.stock_us_daily(symbol=symbol.upper().replace(".US", ""))
    except Exception:
        return []
    if frame.empty:
        return []
    start_iso = _iso_date(start)
    end_iso = _iso_date(end)
    rows = []
    for _, row in frame.iterrows():
        bar_date = str(row.get("date"))[:10]
        if start_iso and bar_date < start_iso:
            continue
        if end_iso and bar_date > end_iso:
            continue
        rows.append(
            {
                "bar_date": bar_date,
                "open": _maybe_float(row.get("open")),
                "high": _maybe_float(row.get("high")),
                "low": _maybe_float(row.get("low")),
                "close": _maybe_float(row.get("close")),
                "volume": _maybe_float(row.get("volume")),
            }
        )
    return rows


def _fetch_akshare_cn_futures_daily(
    symbol: str,
    start: date | str | None,
    end: date | str | None,
) -> list[dict[str, Any]]:
    try:
        import akshare as ak
    except ImportError:
        return []
    code = symbol.split(".", 1)[0]
    try:
        frame = ak.futures_zh_daily_sina(symbol=code)
    except Exception:
        return []
    if frame.empty:
        return []
    return _daily_rows_from_frame(frame, start=start, end=end)


def _ak_date(value: date | str | None) -> str:
    if value is None:
        return "20000101"
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")[:8]


def _iso_date(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _looks_like_us_symbol(symbol: str) -> bool:
    return symbol.replace("-", "").isalnum() and "." not in symbol and not symbol.startswith("^")


def _looks_like_hk_counter(code: str, asset_name: str) -> bool:
    if not code.isdigit() or not code.startswith("00"):
        return False
    name = asset_name.lower()
    return any(keyword in name for keyword in ["hk", "hkd", "hong kong", "hang seng", "恒生", "港股"])


def _forex_symbol(code: str, asset_name: str) -> str | None:
    normalized_code = code.replace("/", "").replace("-", "").upper()
    normalized_name = asset_name.replace("/", "").replace("-", "").replace(" ", "").upper()
    currency_codes = {
        "AUD",
        "BRL",
        "CAD",
        "CHF",
        "CNH",
        "CNY",
        "EUR",
        "GBP",
        "HKD",
        "JPY",
        "MXN",
        "NZD",
        "USD",
        "ZAR",
    }
    for value in [normalized_code, normalized_name]:
        if len(value) >= 6:
            pair = value[:6]
            if pair[:3] in currency_codes and pair[3:6] in currency_codes:
                return f"{pair}=X"
    return None


def _continuous_futures_symbol(code: str) -> str | None:
    root = code.split("1!", 1)[0].upper()
    mapping = {
        "ES": "ES=F",
        "NQ": "NQ=F",
        "YM": "YM=F",
        "RTY": "RTY=F",
        "NKD": "NKD=F",
        "ZB": "ZB=F",
        "ZN": "ZN=F",
        "ZF": "ZF=F",
        "ZT": "ZT=F",
        "GC": "GC=F",
        "SI": "SI=F",
        "HG": "HG=F",
        "PL": "PL=F",
        "PA": "PA=F",
        "CL": "CL=F",
        "BZ": "BZ=F",
        "NG": "NG=F",
        "RB": "RB=F",
        "HO": "HO=F",
        "ZC": "ZC=F",
        "ZS": "ZS=F",
        "ZW": "ZW=F",
        "ZL": "ZL=F",
        "ZM": "ZM=F",
        "KE": "KE=F",
        "LE": "LE=F",
        "HE": "HE=F",
        "GF": "GF=F",
        "CC": "CC=F",
        "KC": "KC=F",
        "CT": "CT=F",
        "SB": "SB=F",
        "OJ": "OJ=F",
        "LBS": "LBS=F",
        "6A": "6A=F",
        "6B": "6B=F",
        "6C": "6C=F",
        "6E": "6E=F",
        "6J": "6J=F",
        "6S": "6S=F",
        "6N": "6N=F",
        "6M": "6M=F",
    }
    return mapping.get(root)


def _hk_symbol_for_akshare(symbol: str) -> str:
    code = symbol.split(".", 1)[0]
    return f"{int(code):05d}" if code.isdigit() else code


def _daily_rows_from_frame(
    frame: Any,
    start: date | str | None = None,
    end: date | str | None = None,
) -> list[dict[str, Any]]:
    start_iso = _iso_date(start)
    end_iso = _iso_date(end)
    rows = []
    for _, row in frame.iterrows():
        bar_date = str(_first_present(row, "日期", "date", "Date"))[:10]
        if start_iso and bar_date < start_iso:
            continue
        if end_iso and bar_date > end_iso:
            continue
        rows.append(
            {
                "bar_date": bar_date,
                "open": _maybe_float(_first_present(row, "开盘", "open", "Open")),
                "high": _maybe_float(_first_present(row, "最高", "high", "High")),
                "low": _maybe_float(_first_present(row, "最低", "low", "Low")),
                "close": _maybe_float(_first_present(row, "收盘", "close", "Close")),
                "volume": _maybe_float(_first_present(row, "成交量", "volume", "Volume")),
            }
        )
    return rows


def _first_present(row: Any, *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _maybe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

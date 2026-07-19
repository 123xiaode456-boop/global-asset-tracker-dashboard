from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .database import AssetDatabase, ImportResult, asset_identifiers_match, make_asset_key
from .market_data import fetch_price_history, guess_symbol_candidates
from .domestic_futures import is_domestic_commodity_future
from .parsers import ParsedDataset, parse_dataset_file
from .reports import write_markdown_report
from .rules import summarize_rows


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "processed" / "signals.sqlite"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "reports"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"


@dataclass(frozen=True)
class FetchPriceResult:
    asset_identifier: str
    asset_code: str
    market_symbol: str | None
    inserted_rows: int
    status: str
    message: str


def run_import(
    paths: list[str | Path],
    db_path: str | Path = DEFAULT_DB,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
    archive_raw: bool = False,
) -> list[ImportResult]:
    db = AssetDatabase(db_path)
    db.initialize()
    results: list[ImportResult] = []

    for source in _expand_paths(paths):
        import_path = _archive_source(source) if archive_raw else source
        parsed = parse_dataset_file(import_path)
        result = db.import_parsed_dataset(parsed, import_path)
        results.append(result)
        if result.dataset_type != "momentum":
            rows = db.get_observations_for_date(result.dataset_date, result.dataset_type)
            write_markdown_report(
                dataset_date=result.dataset_date,
                dataset_type=result.dataset_type,
                summary=summarize_rows(rows),
                report_dir=report_dir,
            )

    return results


def run_fetch_prices(
    db_path: str | Path = DEFAULT_DB,
    asset_identifier: str | None = None,
    dataset_type: str | None = None,
    asset_kind: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
    force_refresh: bool = False,
    missing_only: bool = False,
) -> list[FetchPriceResult]:
    db = AssetDatabase(db_path)
    db.initialize()
    rows = db.get_latest_observations(dataset_type)
    if asset_identifier:
        rows = [
            row
            for row in rows
            if row.get("asset_key") == asset_identifier or row.get("asset_code") == asset_identifier
        ]
    if asset_kind:
        rows = [row for row in rows if _matches_asset_kind(row, asset_kind)]
    if missing_only:
        rows = [row for row in rows if not _has_price_cached_through_signal_date(db, row)]
    if limit is not None:
        rows = rows[:limit]

    results: list[FetchPriceResult] = []
    seen_asset_keys: set[str] = set()
    for row in rows:
        key = row.get("asset_key") or make_asset_key(row["asset_code"], row["asset_name"])
        if key in seen_asset_keys:
            continue
        seen_asset_keys.add(key)
        mapping = db.get_symbol_mapping(key) or db.get_symbol_mapping(row["asset_code"])
        mapped_symbol = mapping.get("market_symbol") if mapping else None
        candidates = [mapped_symbol] if mapped_symbol else guess_symbol_candidates(row)
        candidates = [symbol for symbol in candidates if symbol]
        if not candidates:
            _append_fetch_result(
                results,
                db,
                row,
                FetchPriceResult(key, row["asset_code"], None, 0, "skipped", "no_free_source_candidate"),
                start,
                end,
            )
            continue
        if not force_refresh:
            cached_through = _latest_price_date_for_asset(db, key, row["asset_code"])
            signal_date = str(row.get("dataset_date") or "")
            if cached_through and signal_date and cached_through >= signal_date:
                _append_fetch_result(
                    results,
                    db,
                    row,
                    FetchPriceResult(
                        key,
                        row["asset_code"],
                        candidates[0],
                        0,
                        "cached",
                        f"price_cached_through={cached_through}",
                    ),
                    start,
                    end,
                )
                continue
        errors = []
        empty_symbols = []
        for market_symbol in candidates:
            try:
                bars = fetch_price_history(row, start=start, end=end, market_symbol=market_symbol)
            except Exception as exc:
                errors.append(f"{market_symbol}: {exc}")
                continue
            if not bars:
                empty_symbols.append(market_symbol)
                continue
            source = (mapping or {}).get("price_source") or _price_source_for_symbol(market_symbol)
            inserted = db.upsert_price_bars(key, bars, source)
            _append_fetch_result(
                results,
                db,
                row,
                FetchPriceResult(key, row["asset_code"], market_symbol, inserted, "fetched", ""),
                start,
                end,
            )
            break
        else:
            market_symbol = candidates[-1]
            if errors and len(errors) == len(candidates):
                _append_fetch_result(
                    results,
                    db,
                    row,
                    FetchPriceResult(key, row["asset_code"], market_symbol, 0, "error", "; ".join(errors)),
                    start,
                    end,
                )
            else:
                message = f"tried={','.join(empty_symbols + [error.split(':', 1)[0] for error in errors])}"
                _append_fetch_result(
                    results,
                    db,
                    row,
                    FetchPriceResult(key, row["asset_code"], market_symbol, 0, "empty", message),
                    start,
                    end,
                )
    return results


def run_import_prices(
    db_path: str | Path = DEFAULT_DB,
    asset_identifier: str = "",
    csv_path: str | Path = "",
    source: str = "manual_csv",
) -> FetchPriceResult:
    db = AssetDatabase(db_path)
    db.initialize()
    row = _find_latest_asset_row(db, asset_identifier)
    if row is None:
        if "|" in asset_identifier:
            asset_code, asset_name = asset_identifier.split("|", 1)
        else:
            asset_code, asset_name = asset_identifier, asset_identifier
        key = make_asset_key(asset_code, asset_name)
        dataset_date = None
    else:
        asset_code = row["asset_code"]
        asset_name = row["asset_name"]
        key = row.get("asset_key") or make_asset_key(asset_code, asset_name)
        dataset_date = row.get("dataset_date")

    bars = _read_price_csv(csv_path)
    inserted = db.upsert_price_bars(key, bars, source)
    result = FetchPriceResult(
        asset_identifier=key,
        asset_code=asset_code,
        market_symbol=source,
        inserted_rows=inserted,
        status="imported",
        message=f"manual_csv_rows={inserted}",
    )
    db.record_price_fetch_log(
        asset_key=key,
        asset_code=asset_code,
        asset_name=asset_name,
        dataset_date=dataset_date,
        market_symbol=source,
        status=result.status,
        message=result.message,
        start_date=bars[0]["bar_date"] if bars else None,
        end_date=bars[-1]["bar_date"] if bars else None,
    )
    return result


def run_refresh_names(db_path: str | Path = DEFAULT_DB) -> dict[str, int]:
    db = AssetDatabase(db_path)
    db.initialize()
    return db.refresh_asset_name_translations()


def run_map_symbol(
    db_path: str | Path = DEFAULT_DB,
    asset_identifier: str = "",
    market_symbol: str = "",
    price_source: str = "yfinance",
    note: str = "",
) -> dict:
    db = AssetDatabase(db_path)
    db.initialize()
    row = _find_latest_asset_row(db, asset_identifier)
    if row is None:
        if "|" in asset_identifier:
            asset_code, asset_name = asset_identifier.split("|", 1)
        else:
            asset_code, asset_name = asset_identifier, asset_identifier
        key = make_asset_key(asset_code, asset_name)
    else:
        asset_code = row["asset_code"]
        asset_name = row["asset_name"]
        key = row.get("asset_key") or make_asset_key(asset_code, asset_name)
    db.upsert_symbol_mapping(
        asset_code=key,
        asset_name=asset_name,
        market_symbol=market_symbol,
        price_source=price_source,
        status="mapped",
        note=note,
    )
    mapping = db.get_symbol_mapping(key)
    if mapping is None:
        raise RuntimeError(f"Failed to save mapping for {key}")
    return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import and summarize Knowledge Planet asset datasets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import PDF/XLSX datasets and generate reports.")
    import_parser.add_argument("paths", nargs="+", help="Dataset files or directories.")
    import_parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    import_parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Markdown report directory.")
    import_parser.add_argument("--archive-raw", action="store_true", help="Copy source files into data/raw/YYYY-MM-DD before import.")

    init_parser = subparsers.add_parser("init-db", help="Create the SQLite schema.")
    init_parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")

    refresh_names_parser = subparsers.add_parser("refresh-names", help="Refresh Chinese asset names for imported observations.")
    refresh_names_parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")

    price_parser = subparsers.add_parser("fetch-prices", help="Fetch daily OHLCV bars for latest observations.")
    price_parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    price_parser.add_argument("--asset", help="Asset code or asset_key, for example SPY or SPY|SPDR S&P 500 ETF Trust.")
    price_parser.add_argument(
        "--dataset-type",
        choices=["core", "betting", "domestic_main"],
        help="Limit to one dataset type.",
    )
    price_parser.add_argument(
        "--asset-kind",
        choices=["us-like", "us-etf", "six-digit", "futures", "domestic-futures", "no-candidate"],
        help="Limit fetches to one asset code family.",
    )
    price_parser.add_argument("--start", help="Start date, YYYY-MM-DD.")
    price_parser.add_argument("--end", help="End date, YYYY-MM-DD.")
    price_parser.add_argument("--limit", type=int, help="Limit number of latest observations to fetch.")
    price_parser.add_argument("--force-refresh", action="store_true", help="Fetch even when cached prices already cover the latest signal date.")
    price_parser.add_argument("--missing-only", action="store_true", help="Apply --limit only to assets without prices through the latest signal date.")

    map_parser = subparsers.add_parser("map-symbol", help="Manually map an asset to a price data symbol.")
    map_parser.add_argument("asset", help="Asset code or asset_key, for example SPY or SPY|SPDR S&P 500 ETF Trust.")
    map_parser.add_argument("symbol", help="Market data symbol, for example SPY, 159919.SZ, or GC=F.")
    map_parser.add_argument("--source", default="yfinance", help="Price source label: yfinance, akshare, manual, etc.")
    map_parser.add_argument("--note", default="", help="Optional mapping note.")
    map_parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")

    import_prices_parser = subparsers.add_parser("import-prices", help="Import manual OHLCV CSV prices for one asset.")
    import_prices_parser.add_argument("asset", help="Asset code or asset_key, for example SPY or SPY|SPDR S&P 500 ETF Trust.")
    import_prices_parser.add_argument("csv", help="CSV file with date/open/high/low/close/volume columns.")
    import_prices_parser.add_argument("--source", default="manual_csv", help="Price source label stored with imported bars.")
    import_prices_parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")

    args = parser.parse_args(argv)
    if args.command == "init-db":
        AssetDatabase(args.db).initialize()
        print(f"Initialized database: {args.db}")
        return 0

    if args.command == "import":
        results = run_import(
            args.paths,
            db_path=args.db,
            report_dir=args.report_dir,
            archive_raw=args.archive_raw,
        )
        for result in results:
            status = "duplicate" if result.duplicate else "imported"
            print(f"{status}: {result.dataset_date} {result.dataset_type} rows={result.inserted_rows}")
        return 0

    if args.command == "refresh-names":
        counts = run_refresh_names(db_path=args.db)
        print(f"refreshed-names: assets={counts['assets']} observations={counts['observations']}")
        return 0

    if args.command == "fetch-prices":
        results = run_fetch_prices(
            db_path=args.db,
            asset_identifier=args.asset,
            dataset_type=args.dataset_type,
            asset_kind=args.asset_kind,
            start=args.start,
            end=args.end,
            limit=args.limit,
            force_refresh=args.force_refresh,
            missing_only=args.missing_only,
        )
        for result in results:
            print(
                f"{result.status}: {result.asset_identifier} symbol={result.market_symbol or '-'} rows={result.inserted_rows} {result.message}"
            )
        return 0

    if args.command == "map-symbol":
        mapping = run_map_symbol(
            db_path=args.db,
            asset_identifier=args.asset,
            market_symbol=args.symbol,
            price_source=args.source,
            note=args.note,
        )
        print(
            f"mapped: {mapping['asset_code']} -> {mapping['market_symbol']} source={mapping['price_source']}"
        )
        return 0

    if args.command == "import-prices":
        result = run_import_prices(
            db_path=args.db,
            asset_identifier=args.asset,
            csv_path=args.csv,
            source=args.source,
        )
        print(
            f"{result.status}: {result.asset_identifier} source={args.source} rows={result.inserted_rows}"
        )
        return 0

    return 1


def _expand_paths(paths: list[str | Path]) -> list[Path]:
    expanded: list[Path] = []
    for value in paths:
        path = Path(value)
        if path.is_dir():
            expanded.extend(sorted(p for p in path.iterdir() if p.suffix.lower() in {".pdf", ".xlsx", ".xls"}))
        else:
            expanded.append(path)
    return expanded


def _archive_source(source: Path) -> Path:
    parsed_metadata = _metadata_for_archive(source)
    target_dir = DEFAULT_RAW_DIR / parsed_metadata.metadata.dataset_date.isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if source.resolve() == target.resolve():
        return target

    if target.exists():
        if _file_sha256(source) == _file_sha256(target):
            return target
        target = _unique_archive_target(target, source)

    shutil.copy2(source, target)
    return target


def _metadata_for_archive(source: Path) -> ParsedDataset:
    return parse_dataset_file(source)


def _unique_archive_target(target: Path, source: Path) -> Path:
    digest = _file_sha256(source)[:8]
    candidate = target.with_name(f"{target.stem}-{digest}{target.suffix}")
    counter = 2
    while candidate.exists() and _file_sha256(candidate) != _file_sha256(source):
        candidate = target.with_name(f"{target.stem}-{digest}-{counter}{target.suffix}")
        counter += 1
    return candidate


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _price_source_for_symbol(symbol: str) -> str:
    if symbol.endswith((".SZ", ".SS")):
        return "akshare"
    return "yfinance"


def _find_latest_asset_row(db: AssetDatabase, asset_identifier: str) -> dict | None:
    rows = db.get_latest_observations()
    for row in rows:
        if row.get("asset_key") == asset_identifier or row.get("asset_code") == asset_identifier:
            return row
    return None


def _read_price_csv(csv_path: str | Path) -> list[dict]:
    source = Path(csv_path)
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with source.open("r", encoding=encoding, newline="") as file:
                rows = list(csv.DictReader(file))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Unable to decode CSV file: {source}")

    if not rows:
        raise ValueError(f"No price rows found in CSV file: {source}")

    field_map = _price_csv_field_map(rows[0].keys())
    if "bar_date" not in field_map or "close" not in field_map:
        raise ValueError("Price CSV must contain date and close columns.")

    bars: list[dict] = []
    for row in rows:
        bar_date = _parse_price_date(row.get(field_map["bar_date"]))
        close = _parse_optional_float(row.get(field_map["close"]))
        if close is None:
            continue
        bars.append(
            {
                "bar_date": bar_date,
                "open": _parse_optional_float(row.get(field_map.get("open", ""))),
                "high": _parse_optional_float(row.get(field_map.get("high", ""))),
                "low": _parse_optional_float(row.get(field_map.get("low", ""))),
                "close": close,
                "volume": _parse_optional_float(row.get(field_map.get("volume", ""))),
            }
        )

    if not bars:
        raise ValueError(f"No usable price rows found in CSV file: {source}")
    return sorted(bars, key=lambda row: row["bar_date"])


def _price_csv_field_map(headers) -> dict[str, str]:
    aliases = {
        "bar_date": {"date", "datetime", "time", "bar_date", "bardate", "日期", "交易日期", "时间"},
        "open": {"open", "开盘", "开盘价", "开"},
        "high": {"high", "最高", "最高价", "高"},
        "low": {"low", "最低", "最低价", "低"},
        "close": {"close", "adjclose", "adj_close", "收盘", "收盘价", "收", "最新价"},
        "volume": {"volume", "vol", "成交量", "成交量股", "量"},
    }
    normalized = {_normalize_csv_header(header): header for header in headers}
    field_map: dict[str, str] = {}
    for canonical, names in aliases.items():
        for name in names:
            if name in normalized:
                field_map[canonical] = normalized[name]
                break
    return field_map


def _normalize_csv_header(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
    )


def _parse_price_date(value) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Price CSV contains an empty date value.")
    text = text.split(" ", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(value).strip()).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"Unable to parse price date: {value}") from exc


def _parse_optional_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "nan", "NaN", "N/A", "null"}:
        return None
    return float(text)


def _append_fetch_result(
    results: list[FetchPriceResult],
    db: AssetDatabase,
    row: dict,
    result: FetchPriceResult,
    start: str | None,
    end: str | None,
) -> None:
    results.append(result)
    db.record_price_fetch_log(
        asset_key=result.asset_identifier,
        asset_code=result.asset_code,
        asset_name=row.get("asset_name"),
        dataset_date=row.get("dataset_date"),
        market_symbol=result.market_symbol,
        status=result.status,
        message=result.message,
        start_date=start,
        end_date=end,
    )


def _latest_price_date_for_asset(db: AssetDatabase, asset_key: str, asset_code: str) -> str | None:
    with db.connect() as connection:
        rows = connection.execute(
            """
            SELECT asset_code, MAX(bar_date) AS latest_date FROM price_bars
            WHERE asset_code IN (?, ?) OR asset_code LIKE ?
            GROUP BY asset_code
            """,
            (asset_key, asset_code, f"{asset_code}|%"),
        ).fetchall()
    dates = [
        row["latest_date"]
        for row in rows
        if row["latest_date"] and asset_identifiers_match(asset_key, str(row["asset_code"]), asset_code)
    ]
    return max(dates) if dates else None


def _has_price_cached_through_signal_date(db: AssetDatabase, row: dict) -> bool:
    key = row.get("asset_key") or make_asset_key(row["asset_code"], row["asset_name"])
    cached_through = _latest_price_date_for_asset(db, str(key), str(row["asset_code"]))
    signal_date = str(row.get("dataset_date") or "")
    return bool(cached_through and signal_date and cached_through >= signal_date)


def _matches_asset_kind(row: dict, asset_kind: str) -> bool:
    code = str(row.get("asset_code", "")).strip()
    candidates = guess_symbol_candidates(row)
    if asset_kind == "us-like":
        return bool(code) and not code.isdigit() and "!" not in code and code.replace("-", "").isalnum() and len(code) <= 8
    if asset_kind == "us-etf":
        return _looks_like_us_etf(row)
    if asset_kind == "six-digit":
        return code.isdigit() and len(code) == 6
    if asset_kind == "futures":
        return "!" in code
    if asset_kind == "domestic-futures":
        return is_domestic_commodity_future(row)
    if asset_kind == "no-candidate":
        return not candidates
    return True


def _looks_like_us_etf(row: dict) -> bool:
    code = str(row.get("asset_code", "")).strip()
    name = str(row.get("asset_name", "")).strip().upper()
    if not code or code.isdigit() or "!" in code or not code.replace("-", "").isalnum() or len(code) > 8:
        return False
    if "/" in name or "US DOLLAR" in name or "U.S. DOLLAR" in name or "TETHER" in name:
        return False
    if "GOVERNMENT BONDS YIELD" in name or name.endswith(" INDEX") or " CASH" in name:
        return False
    fund_markers = [
        "ETF",
        "FUND",
        "TRUST",
        "ETN",
        "SHARES",
        "PROSHARES",
        "ISHARES",
        "VANGUARD",
        "VANECK",
        "SPDR",
        "INVESCO",
        "GLOBAL X",
        "DIREXION",
        "WISDOMTREE",
        "FIRST TRUST",
        "FIDELITY",
        "SCHWAB",
    ]
    return any(marker in name for marker in fund_markers)

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from asset_tracker.cli import DEFAULT_DB
from asset_tracker.dashboard_data import load_dashboard_snapshot
from asset_tracker.database import AssetDatabase
from asset_tracker.domestic_futures import domestic_futures_symbol, is_domestic_commodity_future
from asset_tracker.futures_quadrant import load_futures_commodity_trajectories
from asset_tracker.parsers import MOMENTUM_CANONICAL_COLUMNS
from asset_tracker.rules import summarize_rows


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = PROJECT_ROOT / "site"


def export_static_site(
    db_path: str | Path = DEFAULT_DB,
    site_dir: str | Path = DEFAULT_SITE_DIR,
    commodity_only: bool = False,
) -> Path:
    db_path = Path(db_path)
    site_dir = Path(site_dir)
    data_dir = site_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_static_payload(db_path, commodity_only=commodity_only)
    output = data_dir / "app-data.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    export_static_shards(payload, data_dir)
    return output


def export_static_shards(payload: dict[str, Any], data_dir: str | Path) -> Path:
    """Write the same logical dataset as small, lazy-loadable JSON files.

    The monolithic ``app-data.json`` remains a local rollback artifact.  The
    browser loads ``manifest.json`` and fetches the requested date/view only.
    Repeated snapshot summaries and momentum history groupings are derivable
    from the retained rows, so they are not duplicated in the shards.
    """

    data_dir = Path(data_dir)
    for name in ("snapshots", "futures", "momentum"):
        target = data_dir / name
        if target.exists():
            shutil.rmtree(target)

    snapshot_files: dict[str, str] = {}
    for key, snapshot in payload.get("snapshots", {}).items():
        dataset_type, dataset_date = key.split("|", 1)
        relative_path = Path("snapshots") / dataset_type / f"{dataset_date}.json"
        _write_json(data_dir / relative_path, _compact_snapshot(snapshot))
        snapshot_files[key] = relative_path.as_posix()

    futures_files: dict[str, str] = {}
    for dataset_date, items in payload.get("futuresByDate", {}).items():
        relative_path = Path("futures") / f"{dataset_date}.json"
        _write_json(data_dir / relative_path, items)
        futures_files[dataset_date] = relative_path.as_posix()

    momentum_files: dict[str, str] = {}
    for dataset_date, rows in payload.get("momentumByDate", {}).items():
        relative_path = Path("momentum") / f"{dataset_date}.json"
        _write_json(data_dir / relative_path, rows)
        momentum_files[dataset_date] = relative_path.as_posix()

    _write_json(data_dir / "price-histories.json", payload.get("priceHistories", {}))
    _write_json(data_dir / "price-coverage.json", payload.get("priceCoverage", {}))

    momentum_rows = sum(len(rows) for rows in payload.get("momentumByDate", {}).values())
    manifest = {
        "formatVersion": 2,
        "generatedAt": payload.get("generatedAt"),
        "datasetTypes": payload.get("datasetTypes", []),
        "datesByType": payload.get("datesByType", {}),
        "momentumDates": payload.get("momentumDates", []),
        "files": {
            "snapshots": snapshot_files,
            "futuresByDate": futures_files,
            "momentumByDate": momentum_files,
            "priceHistories": "price-histories.json",
            "priceCoverage": "price-coverage.json",
        },
        "retainedData": {
            "snapshotCount": len(snapshot_files),
            "futuresDateCount": len(futures_files),
            "momentumDateCount": len(momentum_files),
            "momentumRowCount": momentum_rows,
            "priceHistoryAssetCount": len(payload.get("priceHistories", {})),
            "priceCoverageAssetCount": len(payload.get("priceCoverage", {})),
        },
        "derivedViews": {
            "momentumHistoryByAsset": "derive from all momentumByDate shards",
            "snapshotOpportunityLists": "derive from each snapshot latestRows",
        },
    }
    manifest_path = data_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "latestDate": snapshot.get("latestDate"),
        "assetCount": snapshot.get("assetCount"),
        "latestCounts": snapshot.get("latestCounts", {}),
        "latestRows": snapshot.get("latestRows", []),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(payload), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_static_payload(db_path: str | Path, commodity_only: bool = False) -> dict[str, Any]:
    db = AssetDatabase(db_path)
    db.initialize()
    all_snapshot = load_dashboard_snapshot(db_path)
    if commodity_only:
        dataset_types = [dataset_type for dataset_type in ("core", "betting") if dataset_type in all_snapshot.dataset_types]
        dataset_options: list[str | None] = list(dataset_types)
    else:
        dataset_types = all_snapshot.dataset_types
        dataset_options = [None, *dataset_types]

    snapshots: dict[str, Any] = {}
    dates_by_type: dict[str, list[str]] = {}
    rows_for_prices: dict[str, dict[str, Any]] = {}
    for dataset_type in dataset_options:
        key_type = dataset_type or "all"
        base_snapshot = load_dashboard_snapshot(db_path, dataset_type)
        dates_by_type[key_type] = base_snapshot.available_dates
        for dataset_date in base_snapshot.available_dates:
            snapshot = load_dashboard_snapshot(db_path, dataset_type, dataset_date)
            snapshot_payload = _snapshot_payload(snapshot)
            if dataset_type:
                snapshot_payload = _merge_momentum_rows(
                    snapshot_payload,
                    [
                        row
                        for row in db.get_momentum_for_date(dataset_date)
                        if row.get("dataset_type") == dataset_type
                    ],
                )
            if dataset_type == "core":
                snapshot_payload = _merge_domestic_main_rows(
                    snapshot_payload,
                    db.get_observations_for_date(dataset_date, "domestic_main"),
                )
            snapshots[f"{key_type}|{dataset_date}"] = snapshot_payload
            for row in snapshot_payload["latestRows"]:
                asset_key = str(row.get("asset_key") or f"{row.get('asset_code')}|{row.get('asset_name')}")
                rows_for_prices[asset_key] = row

    futures_by_date: dict[str, list[dict[str, Any]]] = {}
    for dataset_date in dates_by_type.get("core", []):
        trajectories = [
            *load_futures_commodity_trajectories(db_path, dataset_date=dataset_date, dataset_type="core"),
            *load_futures_commodity_trajectories(
                db_path,
                dataset_date=dataset_date,
                dataset_type="domestic_main",
            ),
        ]
        futures_by_date[dataset_date] = [
            _futures_item_payload(item)
            for item in trajectories
        ]

    momentum_dates = db.list_momentum_dates()
    momentum_by_date = {
        dataset_date: db.get_momentum_for_date(dataset_date)
        for dataset_date in momentum_dates
    }
    momentum_history_by_asset: dict[str, list[dict[str, Any]]] = {}
    for row in db.get_momentum_history():
        momentum_history_by_asset.setdefault(str(row.get("asset_key") or ""), []).append(row)

    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "datasetTypes": dataset_types,
        "datesByType": dates_by_type,
        "snapshots": snapshots,
        "futuresByDate": futures_by_date,
        "momentumDates": momentum_dates,
        "momentumByDate": momentum_by_date,
        "momentumHistoryByAsset": momentum_history_by_asset,
    }
    if commodity_only:
        _filter_payload_to_commodities(payload, rows_for_prices)
    price_histories, price_coverage = _price_payloads(db, rows_for_prices)
    payload["priceHistories"] = price_histories
    payload["priceCoverage"] = price_coverage
    return _clean(payload)


def _snapshot_payload(snapshot) -> dict[str, Any]:
    return {
        "latestDate": snapshot.latest_date,
        "availableDates": snapshot.available_dates,
        "datasetTypes": snapshot.dataset_types,
        "assetCount": snapshot.asset_count,
        "latestCounts": snapshot.latest_counts,
        "latestRows": snapshot.latest_rows,
        "focusWatch": snapshot.focus_watch,
        "riskWatch": snapshot.risk_watch,
        "longOpportunities": snapshot.long_opportunities,
        "shortOpportunities": snapshot.short_opportunities,
    }


def _merge_domestic_main_rows(snapshot: dict[str, Any], domestic_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not domestic_rows:
        return snapshot
    combined_rows = [*snapshot["latestRows"], *domestic_rows]
    summary = summarize_rows(combined_rows)
    return {
        **snapshot,
        "assetCount": len(combined_rows),
        "latestCounts": summary.counts,
        "latestRows": combined_rows,
        "focusWatch": summary.focus_watch,
        "riskWatch": summary.risk_watch,
        "longOpportunities": summary.long_opportunities,
        "shortOpportunities": summary.short_opportunities,
    }


def _merge_momentum_rows(snapshot: dict[str, Any], momentum_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not momentum_rows:
        return snapshot
    momentum_by_key = {
        str(row.get("asset_key") or f"{row.get('asset_code')}|{row.get('asset_name')}"): row
        for row in momentum_rows
    }
    momentum_columns = [
        column for column in MOMENTUM_CANONICAL_COLUMNS if column not in {"asset_code", "asset_name"}
    ]
    merged_rows = []
    for row in snapshot["latestRows"]:
        asset_key = str(row.get("asset_key") or f"{row.get('asset_code')}|{row.get('asset_name')}")
        momentum = momentum_by_key.get(asset_key, {})
        merged_rows.append({**row, **{column: momentum.get(column) for column in momentum_columns}})
    return {**snapshot, "latestRows": merged_rows}


def _futures_item_payload(item) -> dict[str, Any]:
    row = {"asset_code": item.asset_code, "asset_name_cn": item.display_name, "asset_name": item.display_name}
    symbol = domestic_futures_symbol(row)
    return {
        "assetKey": item.asset_key,
        "assetCode": item.asset_code,
        "displayName": item.display_name,
        "group": item.group,
        "isDomestic": is_domestic_commodity_future(row),
        "marketSymbol": symbol,
        "marketSource": "akshare" if symbol else None,
        "points": [asdict(point) for point in item.points],
    }


def _filter_payload_to_commodities(payload: dict[str, Any], rows_for_prices: dict[str, dict[str, Any]]) -> None:
    allowed_keys: set[str] = set()
    futures_by_date = payload.get("futuresByDate", {})
    for items in futures_by_date.values():
        allowed_keys.update(str(item.get("assetKey") or "") for item in items)
    allowed_keys.discard("")

    for asset_key, row in list(rows_for_prices.items()):
        if row.get("dataset_type") != "betting" and asset_key not in allowed_keys:
            rows_for_prices.pop(asset_key, None)


def _price_payloads(
    db: AssetDatabase,
    rows_by_asset_key: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    coverage: dict[str, dict[str, Any]] = {}
    for asset_key, row in rows_by_asset_key.items():
        asset_code = str(row.get("asset_code") or "")
        history = db.get_price_history(asset_key)
        if not history and asset_code:
            history = db.get_price_history(asset_code)
        cleaned_history = [
            {
                "bar_date": item.get("bar_date"),
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close"),
                "volume": item.get("volume"),
                "source": item.get("source"),
            }
            for item in history
        ]
        if cleaned_history:
            histories[asset_key] = cleaned_history
        coverage[asset_key] = {
            "asset_code": asset_code,
            "asset_name": row.get("asset_name"),
            "asset_name_cn": row.get("asset_name_cn"),
            "hasPrice": bool(cleaned_history),
            "priceRows": len(cleaned_history),
            "latestPriceDate": cleaned_history[-1]["bar_date"] if cleaned_history else None,
        }
    return histories, coverage


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, tuple):
        return [_clean(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the dashboard SQLite data to a static GitHub Pages site.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    parser.add_argument("--site-dir", default=str(DEFAULT_SITE_DIR), help="Static site output directory.")
    parser.add_argument("--commodity-only", action="store_true", help="Export only commodity core rows for the v2 static site.")
    args = parser.parse_args(argv)
    output = export_static_site(args.db, args.site_dir, commodity_only=args.commodity_only)
    print(f"exported: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

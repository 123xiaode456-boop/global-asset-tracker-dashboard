from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from asset_tracker.cli import DEFAULT_DB
from asset_tracker.dashboard_data import load_dashboard_snapshot
from asset_tracker.database import AssetDatabase
from asset_tracker.futures_quadrant import load_futures_commodity_trajectories


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = PROJECT_ROOT / "site"


def export_static_site(db_path: str | Path = DEFAULT_DB, site_dir: str | Path = DEFAULT_SITE_DIR) -> Path:
    db_path = Path(db_path)
    site_dir = Path(site_dir)
    data_dir = site_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_static_payload(db_path)
    output = data_dir / "app-data.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return output


def build_static_payload(db_path: str | Path) -> dict[str, Any]:
    db = AssetDatabase(db_path)
    db.initialize()
    all_snapshot = load_dashboard_snapshot(db_path)
    dataset_types = all_snapshot.dataset_types
    dataset_options: list[str | None] = [None, *dataset_types]

    snapshots: dict[str, Any] = {}
    dates_by_type: dict[str, list[str]] = {}
    rows_for_prices: dict[str, dict[str, Any]] = {}
    for dataset_type in dataset_options:
        key_type = dataset_type or "all"
        base_snapshot = load_dashboard_snapshot(db_path, dataset_type)
        dates_by_type[key_type] = base_snapshot.available_dates
        for dataset_date in base_snapshot.available_dates:
            snapshot = load_dashboard_snapshot(db_path, dataset_type, dataset_date)
            snapshots[f"{key_type}|{dataset_date}"] = _snapshot_payload(snapshot)
            for row in snapshot.latest_rows:
                asset_key = str(row.get("asset_key") or f"{row.get('asset_code')}|{row.get('asset_name')}")
                rows_for_prices[asset_key] = row

    futures_by_date: dict[str, list[dict[str, Any]]] = {}
    for dataset_date in dates_by_type.get("core", []):
        trajectories = load_futures_commodity_trajectories(db_path, dataset_date=dataset_date, dataset_type="core")
        futures_by_date[dataset_date] = [
            {
                "assetKey": item.asset_key,
                "assetCode": item.asset_code,
                "displayName": item.display_name,
                "group": item.group,
                "points": [asdict(point) for point in item.points],
            }
            for item in trajectories
        ]

    price_histories, price_coverage = _price_payloads(db, rows_for_prices)

    return _clean(
        {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "datasetTypes": dataset_types,
            "datesByType": dates_by_type,
            "snapshots": snapshots,
            "futuresByDate": futures_by_date,
            "priceHistories": price_histories,
            "priceCoverage": price_coverage,
        }
    )


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
    args = parser.parse_args(argv)
    output = export_static_site(args.db, args.site_dir)
    print(f"exported: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

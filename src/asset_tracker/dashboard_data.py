from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import (
    QuadrantPoint,
    TradeDecision,
    build_quadrant_trajectory,
    classify_trade_decision,
    infer_quadrant_centers,
)
from .database import AssetDatabase
from .market_data import guess_symbol_candidates
from .rules import summarize_rows


@dataclass(frozen=True)
class DashboardSnapshot:
    latest_date: str | None
    available_dates: list[str]
    dataset_types: list[str]
    asset_count: int
    latest_counts: dict[str, int]
    latest_rows: list[dict[str, Any]]
    focus_watch: list[dict[str, Any]]
    risk_watch: list[dict[str, Any]]
    long_opportunities: list[dict[str, Any]]
    short_opportunities: list[dict[str, Any]]


@dataclass(frozen=True)
class AssetPanelData:
    asset_code: str
    selected_date: str | None
    signal_history: list[dict[str, Any]]
    price_history: list[dict[str, Any]]
    unmapped_price: bool
    latest_signal: dict[str, Any] | None
    trade_decision: TradeDecision
    opportunity: dict[str, Any] | None
    quadrant_trajectory: list[QuadrantPoint]


@dataclass(frozen=True)
class PriceCoverageSummary:
    latest_date: str | None
    total_assets: int
    assets_with_price: int
    assets_without_price: int
    coverage_ratio: float
    missing_rows: list[dict[str, Any]]


def load_dashboard_snapshot(
    db_path: str | Path,
    dataset_type: str | None = None,
    dataset_date: str | None = None,
) -> DashboardSnapshot:
    db = AssetDatabase(db_path)
    db.initialize()
    available_dates = db.list_dataset_dates(dataset_type)
    selected_date = dataset_date or db.get_latest_date(dataset_type)
    latest_rows = db.get_observations_for_date(selected_date, dataset_type) if selected_date else []
    summary = summarize_rows(latest_rows)
    return DashboardSnapshot(
        latest_date=selected_date,
        available_dates=available_dates,
        dataset_types=db.get_dataset_types(),
        asset_count=db.count_assets(),
        latest_counts=summary.counts,
        latest_rows=latest_rows,
        focus_watch=summary.focus_watch,
        risk_watch=summary.risk_watch,
        long_opportunities=summary.long_opportunities,
        short_opportunities=summary.short_opportunities,
    )


def load_price_coverage(
    db_path: str | Path,
    dataset_type: str | None = None,
    dataset_date: str | None = None,
) -> PriceCoverageSummary:
    db = AssetDatabase(db_path)
    db.initialize()
    selected_date = dataset_date or db.get_latest_date(dataset_type)
    source_rows = db.get_observations_for_date(selected_date, dataset_type) if selected_date else []
    rows = _dedupe_asset_rows(source_rows)
    latest_fetch_logs = db.get_latest_price_fetch_logs([str(row.get("asset_key") or "") for row in rows])
    missing_rows = []
    assets_with_price = 0
    for row in rows:
        asset_key = str(row.get("asset_key") or "")
        asset_code = str(row.get("asset_code") or "")
        if db.get_price_history(asset_key or asset_code):
            assets_with_price += 1
            continue
        candidates = guess_symbol_candidates(row)
        latest_log = latest_fetch_logs.get(asset_key, {})
        missing_rows.append(
            {
                "asset_key": asset_key,
                "asset_code": asset_code,
                "asset_name": row.get("asset_name"),
                "asset_name_cn": row.get("asset_name_cn"),
                "asset_name_translation_status": row.get("asset_name_translation_status"),
                "dataset_type": row.get("dataset_type"),
                "day_trend": row.get("day_trend"),
                "relative_state": row.get("relative_state"),
                "capital_state": row.get("capital_state"),
                "candidate_symbols": ", ".join(candidates),
                "price_status": "缺行情",
                "last_fetch_status": latest_log.get("status", ""),
                "last_fetch_message": latest_log.get("message", ""),
                "last_fetch_symbol": latest_log.get("market_symbol", "") or "",
                "last_fetch_at": latest_log.get("attempted_at", ""),
            }
        )
    total_assets = len(rows)
    assets_without_price = total_assets - assets_with_price
    coverage_ratio = assets_with_price / total_assets if total_assets else 0.0
    return PriceCoverageSummary(
        latest_date=selected_date,
        total_assets=total_assets,
        assets_with_price=assets_with_price,
        assets_without_price=assets_without_price,
        coverage_ratio=coverage_ratio,
        missing_rows=missing_rows,
    )


def get_asset_panel_data(
    db_path: str | Path,
    asset_code: str,
    dataset_date: str | None = None,
    dataset_type: str | None = None,
) -> AssetPanelData:
    db = AssetDatabase(db_path)
    db.initialize()
    signal_history = db.get_asset_history(asset_code)
    if dataset_type:
        signal_history = [row for row in signal_history if row.get("dataset_type") == dataset_type]
    price_history = db.get_price_history(asset_code)
    selected_date = dataset_date or (signal_history[-1]["dataset_date"] if signal_history else None)
    latest_signal = _select_signal_for_date(signal_history, selected_date)
    opportunity = _find_asset_opportunity(db, latest_signal, selected_date, dataset_type)
    center_dataset_type = dataset_type or str((latest_signal or {}).get("dataset_type") or "core")
    center_rows = [
        row
        for date_key in db.list_dataset_dates(center_dataset_type)
        if selected_date is None or date_key <= selected_date
        for row in db.get_observations_for_date(date_key, center_dataset_type)
    ]
    trajectory_history = [
        row
        for row in signal_history
        if selected_date is None or str(row.get("dataset_date") or "") <= selected_date
    ]
    return AssetPanelData(
        asset_code=asset_code,
        selected_date=selected_date,
        signal_history=signal_history,
        price_history=price_history,
        unmapped_price=len(price_history) == 0,
        latest_signal=latest_signal,
        trade_decision=classify_trade_decision(latest_signal),
        opportunity=opportunity,
        quadrant_trajectory=build_quadrant_trajectory(
            trajectory_history,
            infer_quadrant_centers(center_rows),
        ),
    )


def _dedupe_asset_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"core": 2, "betting": 1}
    by_key: dict[str, tuple[int, int, dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = row.get("asset_key") or f"{row.get('asset_code', '')}|{row.get('asset_name', '')}"
        row_priority = priority.get(str(row.get("dataset_type", "")), 0)
        current = by_key.get(str(key))
        if current is None or (row_priority, -index) > (current[0], current[1]):
            by_key[str(key)] = (row_priority, -index, row)
    return [entry[2] for key, entry in sorted(by_key.items(), key=lambda item: item[0])]


def _select_signal_for_date(history: list[dict[str, Any]], dataset_date: str | None) -> dict[str, Any] | None:
    if not history:
        return None
    if dataset_date is None:
        return history[-1]
    rows = [row for row in history if row.get("dataset_date") == dataset_date]
    if not rows:
        return None
    return _dedupe_asset_rows(rows)[0]


def _find_asset_opportunity(
    db: AssetDatabase,
    latest_signal: dict[str, Any] | None,
    dataset_date: str | None,
    dataset_type: str | None,
) -> dict[str, Any] | None:
    if latest_signal is None or dataset_date is None:
        return None
    rows = db.get_observations_for_date(dataset_date, dataset_type)
    summary = summarize_rows(rows)
    asset_key = str(latest_signal.get("asset_key") or "")
    asset_code = str(latest_signal.get("asset_code") or "")
    for item in [*summary.long_opportunities, *summary.short_opportunities]:
        if item.get("asset_key") == asset_key or item.get("asset_code") == asset_code:
            return item
    decision = classify_trade_decision(latest_signal)
    return {
        "asset_key": asset_key,
        "asset_code": asset_code,
        "asset_name": latest_signal.get("asset_name"),
        "dataset_date": dataset_date,
        "dataset_type": latest_signal.get("dataset_type"),
        "rank": None,
        "score": 0.0,
        "decision_label": decision.label,
        "opportunity_type": "观望",
        "reasons": decision.reason,
    }

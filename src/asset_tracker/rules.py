from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .analysis import classify_trade_decision


FOCUS_RELATIVE_STATES = {"lead", "improving"}
RISK_RELATIVE_STATES = {"lag", "weakening"}


@dataclass(frozen=True)
class DailySummary:
    counts: dict[str, int]
    focus_watch: list[dict[str, Any]]
    risk_watch: list[dict[str, Any]]
    long_opportunities: list[dict[str, Any]]
    short_opportunities: list[dict[str, Any]]
    relative_state_changes: list[dict[str, Any]]
    capital_state_changes: list[dict[str, Any]]
    strongest: list[dict[str, Any]]
    weakest: list[dict[str, Any]]


def summarize_rows(rows: list[dict[str, Any]], max_items: int = 20) -> DailySummary:
    focus = []
    risk = []
    relative_changes = []
    capital_changes = []

    for row in rows:
        relative_state = _state(row.get("relative_state"))
        capital_state = _text(row.get("capital_state"))
        week_trend = _text(row.get("week_trend"))

        if (
            relative_state in FOCUS_RELATIVE_STATES
            and capital_state == "加杠杆"
            and week_trend == "上行趋势"
        ):
            focus.append(_summary_item(row))

        if (
            relative_state in RISK_RELATIVE_STATES
            and capital_state == "去杠杆"
            and week_trend == "下行趋势"
        ):
            risk.append(_summary_item(row))

        if _to_int(row.get("relative_state_duration")) == 1:
            relative_changes.append(_summary_item(row))

        if _to_int(row.get("capital_state_duration")) == 1:
            capital_changes.append(_summary_item(row))

    sorted_rows = sorted(rows, key=lambda item: _to_float(item.get("relative_strength")), reverse=True)
    weakest_rows = list(reversed(sorted_rows))

    return DailySummary(
        counts={
            "total": len(rows),
            "capital_add": sum(1 for row in rows if _text(row.get("capital_state")) == "加杠杆"),
            "capital_reduce": sum(1 for row in rows if _text(row.get("capital_state")) == "去杠杆"),
            "relative_lead": sum(1 for row in rows if _state(row.get("relative_state")) == "lead"),
            "relative_improving": sum(1 for row in rows if _state(row.get("relative_state")) == "improving"),
            "relative_lag": sum(1 for row in rows if _state(row.get("relative_state")) == "lag"),
            "relative_weakening": sum(1 for row in rows if _state(row.get("relative_state")) == "weakening"),
        },
        focus_watch=sorted(focus, key=_watch_sort_key, reverse=True)[:max_items],
        risk_watch=sorted(risk, key=_risk_sort_key)[:max_items],
        long_opportunities=rank_opportunities(rows, "long", max_items),
        short_opportunities=rank_opportunities(rows, "short", max_items),
        relative_state_changes=relative_changes[:max_items],
        capital_state_changes=capital_changes[:max_items],
        strongest=[_summary_item(row) for row in sorted_rows[:max_items]],
        weakest=[_summary_item(row) for row in weakest_rows[:max_items]],
    )


def rank_opportunities(rows: list[dict[str, Any]], action: str, max_items: int = 20) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        decision = classify_trade_decision(row)
        if decision.action != action:
            continue
        if action == "long":
            score, reasons = _long_score(row)
            opportunity_type = "做多机会"
        elif action == "short":
            score, reasons = _short_score(row)
            opportunity_type = "做空/风险机会"
        else:
            continue
        item = {
            **_summary_item(row),
            "asset_key": row.get("asset_key"),
            "dataset_date": row.get("dataset_date"),
            "dataset_type": row.get("dataset_type"),
            "rank": 0,
            "score": round(score, 2),
            "decision_label": decision.label,
            "opportunity_type": opportunity_type,
            "reasons": "；".join(reasons),
        }
        scored.append(item)
    scored.sort(key=lambda item: item["score"], reverse=True)
    for index, item in enumerate(scored[:max_items], start=1):
        item["rank"] = index
    return scored[:max_items]


def _summary_item(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "asset_code",
        "asset_name",
        "asset_name_cn",
        "asset_name_translation_status",
        "day_trend",
        "week_trend",
        "month_trend",
        "relative_state",
        "relative_state_duration",
        "relative_strength",
        "strength_momentum",
        "early_turn",
        "capital_state",
        "capital_state_duration",
        "capital_daily_change",
        "capital_value",
    ]
    return {key: row.get(key) for key in keys if key in row}


def _long_score(row: dict[str, Any]) -> tuple[float, list[str]]:
    score = 100.0
    reasons = ["日趋势上行"]
    if _text(row.get("week_trend")) == "上行趋势":
        score += 25.0
        reasons.append("周趋势上行")
    if _text(row.get("month_trend")) == "上行趋势":
        score += 15.0
        reasons.append("月趋势上行")
    relative_state = _state(row.get("relative_state"))
    if relative_state == "lead":
        score += 24.0
        reasons.append("比价Lead")
    elif relative_state == "improving":
        score += 18.0
        reasons.append("比价Improving")
    if _text(row.get("capital_state")) == "加杠杆":
        score += 25.0
        reasons.append("资金加杠杆")
    score += max(_to_float(row.get("relative_strength")) - 100.0, 0.0) * 2.0
    score += max(_to_float(row.get("strength_momentum")) - 100.0, 0.0) * 2.0
    score += max(_to_float(row.get("capital_daily_change")), 0.0) * 4.0
    score += max(_to_float(row.get("capital_value")) - 50.0, 0.0) * 0.2
    return score, reasons


def _short_score(row: dict[str, Any]) -> tuple[float, list[str]]:
    score = 100.0
    reasons = ["日趋势下行"]
    if _text(row.get("week_trend")) == "下行趋势":
        score += 25.0
        reasons.append("周趋势下行")
    if _text(row.get("month_trend")) == "下行趋势":
        score += 15.0
        reasons.append("月趋势下行")
    relative_state = _state(row.get("relative_state"))
    if relative_state == "lag":
        score += 24.0
        reasons.append("比价Lag")
    elif relative_state == "weakening":
        score += 18.0
        reasons.append("比价Weakening")
    if _text(row.get("capital_state")) == "去杠杆":
        score += 25.0
        reasons.append("资金去杠杆")
    score += max(100.0 - _to_float(row.get("relative_strength")), 0.0) * 2.0
    score += max(100.0 - _to_float(row.get("strength_momentum")), 0.0) * 2.0
    score += max(-_to_float(row.get("capital_daily_change")), 0.0) * 4.0
    score += max(50.0 - _to_float(row.get("capital_value")), 0.0) * 0.2
    return score, reasons


def _watch_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    return (
        _to_float(item.get("capital_daily_change")),
        _to_float(item.get("strength_momentum")),
        _to_float(item.get("relative_strength")),
    )


def _risk_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    return (
        _to_float(item.get("capital_daily_change")),
        _to_float(item.get("relative_strength")),
        _to_float(item.get("strength_momentum")),
    )


def _state(value: Any) -> str:
    return _text(value).lower()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)

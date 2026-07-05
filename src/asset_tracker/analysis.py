from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TradeDecision:
    action: str
    label: str
    reason: str
    color: str


@dataclass(frozen=True)
class QuadrantPoint:
    date: str
    x: float
    y: float
    quadrant: str
    relative_state: str
    relative_strength: float
    strength_momentum: float


def classify_trade_decision(row: dict[str, Any] | None) -> TradeDecision:
    trend = _text((row or {}).get("day_trend"))
    if trend in {"上行趋势", "上涨趋势"}:
        return TradeDecision("long", "可做多", "日级别趋势为上行趋势。", "#2ea043")
    if trend in {"下行趋势", "下跌趋势"}:
        return TradeDecision("short", "可做空", "日级别趋势为下行趋势。", "#d1242f")
    return TradeDecision("wait", "不做/观望", "日级别趋势为无趋势或暂未识别。", "#8c959f")


def build_quadrant_trajectory(history: list[dict[str, Any]]) -> list[QuadrantPoint]:
    points: list[QuadrantPoint] = []
    for row in _one_row_per_date(history):
        rs = _to_float(row.get("relative_strength"))
        momentum = _to_float(row.get("strength_momentum"))
        if rs is None or momentum is None:
            continue
        x = round(rs - 100.0, 6)
        y = round(momentum - 100.0, 6)
        points.append(
            QuadrantPoint(
                date=str(row.get("dataset_date", "")),
                x=x,
                y=y,
                quadrant=classify_quadrant(x, y),
                relative_state=_text(row.get("relative_state")),
                relative_strength=rs,
                strength_momentum=momentum,
            )
        )
    return points


def _one_row_per_date(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"core": 2, "betting": 1}
    by_date: dict[str, tuple[int, int, dict[str, Any]]] = {}
    for index, row in enumerate(history):
        date_key = str(row.get("dataset_date", ""))
        dataset_type = str(row.get("dataset_type", ""))
        row_priority = priority.get(dataset_type, 0)
        current = by_date.get(date_key)
        if current is None or (row_priority, index) > (current[0], current[1]):
            by_date[date_key] = (row_priority, index, row)
    return [entry[2] for _, entry in sorted(by_date.items(), key=lambda item: item[0])]


def classify_quadrant(x: float, y: float) -> str:
    if x >= 0 and y >= 0:
        return "Leading"
    if x < 0 <= y:
        return "Improving"
    if x >= 0 > y:
        return "Weakening"
    return "Lagging"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

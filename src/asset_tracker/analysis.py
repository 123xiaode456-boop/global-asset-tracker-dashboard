from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import median
from typing import Any


QUADRANT_CENTER_CANDIDATES = (0.0, 50.0, 100.0)
QUADRANT_BY_RELATIVE_STATE = {
    "lead": "Leading",
    "leading": "Leading",
    "improving": "Improving",
    "lag": "Lagging",
    "lagging": "Lagging",
    "weakening": "Weakening",
}
QUADRANT_SIGNS = {
    "Leading": (1, 1),
    "Improving": (-1, 1),
    "Lagging": (-1, -1),
    "Weakening": (1, -1),
}


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


def build_quadrant_trajectory(
    history: list[dict[str, Any]],
    centers_by_date: Mapping[str, tuple[float, float]] | None = None,
) -> list[QuadrantPoint]:
    points: list[QuadrantPoint] = []
    dated_rows = _one_row_per_date(history)
    centers = dict(centers_by_date or infer_quadrant_centers(dated_rows))
    for row in dated_rows:
        rs = _to_float(row.get("relative_strength"))
        momentum = _to_float(row.get("strength_momentum"))
        if rs is None or momentum is None:
            continue
        date_key = str(row.get("dataset_date", ""))
        x_center, y_center = centers.get(
            date_key,
            (
                _infer_axis_center([row], "relative_strength", {"lead", "leading", "weakening"}),
                _infer_axis_center([row], "strength_momentum", {"lead", "leading", "improving"}),
            ),
        )
        x = rs - x_center
        y = momentum - y_center
        state_quadrant = relative_state_quadrant(row.get("relative_state"))
        if state_quadrant:
            x_sign, y_sign = QUADRANT_SIGNS[state_quadrant]
            x = _signed_magnitude(x, x_sign)
            y = _signed_magnitude(y, y_sign)
        x = round(x, 6)
        y = round(y, 6)
        points.append(
            QuadrantPoint(
                date=date_key,
                x=x,
                y=y,
                quadrant=state_quadrant or classify_quadrant(x, y),
                relative_state=_text(row.get("relative_state")),
                relative_strength=rs,
                strength_momentum=momentum,
            )
        )
    return points


def infer_quadrant_centers(rows: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row.get("dataset_date", ""))].append(row)
    return {
        date_key: (
            _infer_axis_center(date_rows, "relative_strength", {"lead", "leading", "weakening"}),
            _infer_axis_center(date_rows, "strength_momentum", {"lead", "leading", "improving"}),
        )
        for date_key, date_rows in by_date.items()
        if date_key
    }


def relative_state_quadrant(value: Any) -> str | None:
    return QUADRANT_BY_RELATIVE_STATE.get(_text(value).lower())


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


def _infer_axis_center(
    rows: list[dict[str, Any]],
    value_key: str,
    positive_states: set[str],
) -> float:
    samples: list[tuple[float, bool]] = []
    for row in rows:
        value = _to_float(row.get(value_key))
        state = _text(row.get("relative_state")).lower()
        if value is None or state not in QUADRANT_BY_RELATIVE_STATE:
            continue
        samples.append((value, state in positive_states))
    if not samples:
        return 100.0

    scores = {
        center: sum((value >= center) == expected_positive for value, expected_positive in samples)
        for center in QUADRANT_CENTER_CANDIDATES
    }
    best_score = max(scores.values())
    sample_median = median(value for value, _ in samples)
    return min(
        (center for center, score in scores.items() if score == best_score),
        key=lambda center: (abs(center - sample_median), center),
    )


def _signed_magnitude(value: float, sign: int) -> float:
    magnitude = max(abs(value), 0.000001)
    return magnitude if sign > 0 else -magnitude


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

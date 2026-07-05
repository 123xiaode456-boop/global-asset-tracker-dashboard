from __future__ import annotations

from pathlib import Path
from typing import Any

from .rules import DailySummary


def render_markdown_report(dataset_date: str, dataset_type: str, summary: DailySummary) -> str:
    lines = [
        f"# {dataset_date} {dataset_type} 数据总表观察日报",
        "",
        "> 仅做知识星球数据整理、状态观察和复盘记录，不构成投资建议，不作为买卖依据。",
        "",
        "## 总览",
        "",
        f"- 覆盖标的数：{summary.counts.get('total', 0)}",
        f"- 加杠杆：{summary.counts.get('capital_add', 0)}",
        f"- 去杠杆：{summary.counts.get('capital_reduce', 0)}",
        f"- 比价 Lead / Improving / Lag / Weakening：{summary.counts.get('relative_lead', 0)} / {summary.counts.get('relative_improving', 0)} / {summary.counts.get('relative_lag', 0)} / {summary.counts.get('relative_weakening', 0)}",
        "",
    ]
    lines.extend(_section("重点观察", summary.focus_watch))
    lines.extend(_section("风险观察", summary.risk_watch))
    lines.extend(_section("比价状态新切换", summary.relative_state_changes))
    lines.extend(_section("资金状态新切换", summary.capital_state_changes))
    lines.extend(_section("相对强度靠前", summary.strongest[:10]))
    lines.extend(_section("相对强度靠后", summary.weakest[:10]))
    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(
    dataset_date: str,
    dataset_type: str,
    summary: DailySummary,
    report_dir: str | Path,
) -> Path:
    target_dir = Path(report_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{dataset_date}_{dataset_type}.md"
    target.write_text(render_markdown_report(dataset_date, dataset_type, summary), encoding="utf-8")
    return target


def _section(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["暂无。", ""])
        return lines
    lines.extend(
        [
            "| 代码 | 名称 | 日/周/月趋势 | 比价状态 | 资金状态 | RS | 动量 | 早期转折 | 资金日变动 |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        trend = f"{_v(row, 'day_trend')}/{_v(row, 'week_trend')}/{_v(row, 'month_trend')}"
        relative = f"{_v(row, 'relative_state')}({_v(row, 'relative_state_duration')})"
        capital = f"{_v(row, 'capital_state')}({_v(row, 'capital_state_duration')})"
        lines.append(
            "| {code} | {name} | {trend} | {relative} | {capital} | {rs} | {momentum} | {early} | {capital_change} |".format(
                code=_v(row, "asset_code"),
                name=_v(row, "asset_name"),
                trend=trend,
                relative=relative,
                capital=capital,
                rs=_num(row.get("relative_strength")),
                momentum=_num(row.get("strength_momentum")),
                early=_num(row.get("early_turn")),
                capital_change=_num(row.get("capital_daily_change")),
            )
        )
    lines.append("")
    return lines


def _v(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def _num(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)

from asset_tracker.reports import render_markdown_report
from asset_tracker.rules import summarize_rows


def test_markdown_report_contains_observation_sections_and_disclaimer():
    rows = [
        {
            "asset_code": "AAA",
            "asset_name": "Alpha",
            "week_trend": "上行趋势",
            "day_trend": "上行趋势",
            "month_trend": "无趋势",
            "relative_state": "lead",
            "relative_state_duration": 1,
            "relative_strength": 110.0,
            "strength_momentum": 112.0,
            "early_turn": 115.0,
            "capital_state": "加杠杆",
            "capital_state_duration": 1,
            "capital_daily_change": 2.0,
            "capital_value": 80.0,
        }
    ]

    report = render_markdown_report(
        dataset_date="2026-06-09",
        dataset_type="core",
        summary=summarize_rows(rows),
    )

    assert "# 2026-06-09 core 数据总表观察日报" in report
    assert "## 重点观察" in report
    assert "AAA" in report
    assert "不构成投资建议" in report

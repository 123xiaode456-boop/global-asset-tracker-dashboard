from asset_tracker.rules import summarize_rows


def test_summary_groups_focus_risk_and_state_changes():
    rows = [
        {
            "asset_code": "AAA",
            "asset_name": "Alpha",
            "week_trend": "上行趋势",
            "relative_state": "Improving",
            "relative_state_duration": 1,
            "capital_state": "加杠杆",
            "capital_state_duration": 1,
            "relative_strength": 101.2,
            "strength_momentum": 105.5,
            "early_turn": 110.0,
            "capital_daily_change": 2.3,
        },
        {
            "asset_code": "BBB",
            "asset_name": "Beta",
            "week_trend": "下行趋势",
            "relative_state": "Lag",
            "relative_state_duration": 4,
            "capital_state": "去杠杆",
            "capital_state_duration": 1,
            "relative_strength": 89.0,
            "strength_momentum": 82.0,
            "early_turn": 80.0,
            "capital_daily_change": -3.1,
        },
        {
            "asset_code": "CCC",
            "asset_name": "Gamma",
            "week_trend": "无趋势",
            "relative_state": "Weakening",
            "relative_state_duration": 2,
            "capital_state": "加杠杆",
            "capital_state_duration": 9,
            "relative_strength": 96.0,
            "strength_momentum": 97.0,
            "early_turn": 93.0,
            "capital_daily_change": 0.2,
        },
    ]

    summary = summarize_rows(rows)

    assert [item["asset_code"] for item in summary.focus_watch] == ["AAA"]
    assert [item["asset_code"] for item in summary.risk_watch] == ["BBB"]
    assert [item["asset_code"] for item in summary.relative_state_changes] == ["AAA"]
    assert [item["asset_code"] for item in summary.capital_state_changes] == ["AAA", "BBB"]
    assert summary.counts["total"] == 3
    assert summary.counts["capital_add"] == 2
    assert summary.counts["capital_reduce"] == 1

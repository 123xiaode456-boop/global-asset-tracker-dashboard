from asset_tracker.analysis import (
    build_quadrant_trajectory,
    classify_trade_decision,
    infer_quadrant_centers,
)


def test_classify_trade_decision_maps_day_trend_to_action():
    long_decision = classify_trade_decision({"day_trend": "上行趋势"})
    short_decision = classify_trade_decision({"day_trend": "下行趋势"})
    wait_decision = classify_trade_decision({"day_trend": "无趋势"})

    assert long_decision.action == "long"
    assert long_decision.label == "可做多"
    assert short_decision.action == "short"
    assert short_decision.label == "可做空"
    assert wait_decision.action == "wait"
    assert wait_decision.label == "不做/观望"


def test_classify_trade_decision_handles_unknown_trend_as_wait():
    decision = classify_trade_decision({"day_trend": ""})

    assert decision.action == "wait"
    assert decision.label == "不做/观望"
    assert "无趋势" in decision.reason


def test_classify_trade_decision_accepts_up_down_synonyms():
    long_decision = classify_trade_decision({"day_trend": "上涨趋势"})
    short_decision = classify_trade_decision({"day_trend": "下跌趋势"})

    assert long_decision.action == "long"
    assert long_decision.label == "可做多"
    assert short_decision.action == "short"
    assert short_decision.label == "可做空"


def test_build_quadrant_trajectory_uses_relative_strength_and_momentum():
    history = [
        {
            "dataset_date": "2026-06-09",
            "relative_strength": 96.0,
            "strength_momentum": 104.0,
            "relative_state": "Improving",
        },
        {
            "dataset_date": "2026-06-10",
            "relative_strength": 105.0,
            "strength_momentum": 103.0,
            "relative_state": "lead",
        },
        {
            "dataset_date": "2026-06-11",
            "relative_strength": 104.0,
            "strength_momentum": 97.0,
            "relative_state": "Weakening",
        },
        {
            "dataset_date": "2026-06-12",
            "relative_strength": 95.0,
            "strength_momentum": 94.0,
            "relative_state": "Lag",
        },
    ]

    trajectory = build_quadrant_trajectory(history)

    assert [point.date for point in trajectory] == [
        "2026-06-09",
        "2026-06-10",
        "2026-06-11",
        "2026-06-12",
    ]
    assert [(point.x, point.y, point.quadrant) for point in trajectory] == [
        (-4.0, 4.0, "Improving"),
        (5.0, 3.0, "Leading"),
        (4.0, -3.0, "Weakening"),
        (-5.0, -6.0, "Lagging"),
    ]


def test_build_quadrant_trajectory_keeps_one_point_per_date():
    history = [
        {
            "dataset_date": "2026-06-09",
            "dataset_type": "betting",
            "relative_strength": 96.0,
            "strength_momentum": 104.0,
            "relative_state": "Improving",
        },
        {
            "dataset_date": "2026-06-09",
            "dataset_type": "core",
            "relative_strength": 105.0,
            "strength_momentum": 103.0,
            "relative_state": "lead",
        },
    ]

    trajectory = build_quadrant_trajectory(history)

    assert len(trajectory) == 1
    assert trajectory[0].date == "2026-06-09"
    assert trajectory[0].quadrant == "Leading"


def test_infer_quadrant_centers_supports_legacy_and_current_scales():
    rows = [
        {"dataset_date": "2026-07-17", "relative_strength": 105.0, "strength_momentum": 104.0, "relative_state": "lead"},
        {"dataset_date": "2026-07-17", "relative_strength": 96.0, "strength_momentum": 103.0, "relative_state": "Improving"},
        {"dataset_date": "2026-07-17", "relative_strength": 95.0, "strength_momentum": 94.0, "relative_state": "Lag"},
        {"dataset_date": "2026-07-17", "relative_strength": 104.0, "strength_momentum": 97.0, "relative_state": "Weakening"},
        {"dataset_date": "2026-07-23", "relative_strength": 60.0, "strength_momentum": 5.0, "relative_state": "lead"},
        {"dataset_date": "2026-07-23", "relative_strength": 45.0, "strength_momentum": 8.0, "relative_state": "Improving"},
        {"dataset_date": "2026-07-23", "relative_strength": 40.0, "strength_momentum": -3.0, "relative_state": "Lag"},
        {"dataset_date": "2026-07-23", "relative_strength": 65.0, "strength_momentum": -4.0, "relative_state": "Weakening"},
    ]

    centers = infer_quadrant_centers(rows)

    assert centers["2026-07-17"] == (100.0, 100.0)
    assert centers["2026-07-23"] == (50.0, 0.0)


def test_build_quadrant_trajectory_keeps_source_state_authoritative_after_scale_change():
    history = [
        {
            "dataset_date": "2026-07-23",
            "relative_strength": 45.68932921054105,
            "strength_momentum": 13.22929928047039,
            "relative_state": "Improving",
        }
    ]

    point = build_quadrant_trajectory(history, {"2026-07-23": (50.0, 0.0)})[0]

    assert (point.x, point.y, point.quadrant) == (-4.310671, 13.229299, "Improving")

from asset_tracker.analysis import QuadrantPoint
from asset_tracker.dashboard import (
    _asset_labels,
    _asset_table_frame,
    _filter_asset_frame,
    _filter_asset_rows,
    _market_quadrant_figure,
    _quadrant_figure,
    _quadrant_timeline_figure,
    _unique_asset_rows,
)


def test_quadrant_figure_contains_trajectory_trace():
    points = [
        QuadrantPoint("2026-06-09", -4.0, 4.0, "Improving", "Improving", 96.0, 104.0),
        QuadrantPoint("2026-06-10", 5.0, 3.0, "Leading", "lead", 105.0, 103.0),
    ]

    figure = _quadrant_figure(points)

    assert figure.data[0].name == "象限轨迹"
    assert list(figure.data[0].x) == [-4.0, 5.0]
    assert list(figure.data[0].y) == [4.0, 3.0]
    assert "Leading" in [annotation.text for annotation in figure.layout.annotations]


def test_quadrant_figure_contains_full_four_quadrant_background():
    points = [
        QuadrantPoint("2026-06-09", -4.0, 4.0, "Improving", "Improving", 96.0, 104.0),
        QuadrantPoint("2026-06-10", 5.0, 3.0, "Leading", "lead", 105.0, 103.0),
    ]

    figure = _quadrant_figure(points)

    rectangle_shapes = [shape for shape in figure.layout.shapes if shape.type == "rect"]
    assert len(rectangle_shapes) == 4
    assert {shape.layer for shape in rectangle_shapes} == {"below"}


def test_quadrant_timeline_figure_uses_dates_as_x_axis():
    points = [
        QuadrantPoint("2026-06-09", -4.0, 4.0, "Improving", "Improving", 96.0, 104.0),
        QuadrantPoint("2026-06-10", 5.0, 3.0, "Leading", "lead", 105.0, 103.0),
    ]

    figure = _quadrant_timeline_figure(points)

    assert [trace.name for trace in figure.data] == ["横轴坐标 RS-100", "纵轴坐标 动量-100"]
    assert list(figure.data[0].x) == ["2026-06-09", "2026-06-10"]
    assert list(figure.data[0].y) == [-4.0, 5.0]
    assert list(figure.data[1].y) == [4.0, 3.0]


def test_unique_asset_rows_deduplicates_dropdown_assets():
    rows = [
        {"asset_key": "EFA|iShares MSCI EAFE ETF", "asset_code": "EFA", "asset_name": "iShares MSCI EAFE ETF", "dataset_type": "betting"},
        {"asset_key": "EFA|iShares MSCI EAFE ETF", "asset_code": "EFA", "asset_name": "iShares MSCI EAFE ETF", "dataset_type": "core"},
        {"asset_key": "SPY|SPDR S&P 500 ETF Trust", "asset_code": "SPY", "asset_name": "SPDR S&P 500 ETF Trust", "dataset_type": "core"},
    ]

    unique = _unique_asset_rows(rows)

    assert [row["asset_key"] for row in unique] == [
        "EFA|iShares MSCI EAFE ETF",
        "SPY|SPDR S&P 500 ETF Trust",
    ]
    assert unique[0]["dataset_type"] == "core"


def test_market_quadrant_figure_plots_latest_asset_positions_by_decision():
    rows = [
        {
            "asset_key": "AAA|Alpha",
            "asset_code": "AAA",
            "asset_name": "Alpha",
            "dataset_date": "2026-06-18",
            "day_trend": "上行趋势",
            "relative_strength": 106.0,
            "strength_momentum": 104.0,
            "relative_state": "lead",
        },
        {
            "asset_key": "BBB|Beta",
            "asset_code": "BBB",
            "asset_name": "Beta",
            "dataset_date": "2026-06-18",
            "day_trend": "下行趋势",
            "relative_strength": 95.0,
            "strength_momentum": 96.0,
            "relative_state": "Lag",
        },
        {
            "asset_key": "CCC|Cash",
            "asset_code": "CCC",
            "asset_name": "Cash",
            "dataset_date": "2026-06-18",
            "day_trend": "无趋势",
            "relative_strength": 101.0,
            "strength_momentum": 97.0,
            "relative_state": "Weakening",
        },
    ]

    figure = _market_quadrant_figure(rows, show_labels=True)

    assert [trace.name for trace in figure.data] == ["可做多", "可做空", "不做/观望"]
    assert list(figure.data[0].x) == [6.0]
    assert list(figure.data[0].y) == [4.0]
    assert list(figure.data[0].text) == ["Alpha"]
    assert list(figure.data[1].x) == [-5.0]
    assert list(figure.data[1].y) == [-4.0]
    assert list(figure.data[2].x) == [1.0]
    assert list(figure.data[2].y) == [-3.0]
    assert "Leading" in [annotation.text for annotation in figure.layout.annotations]


def test_asset_labels_prefer_chinese_name_and_keep_original_name():
    rows = [
        {
            "asset_key": "GC1!|Gold Futures",
            "asset_code": "GC1!",
            "asset_name": "Gold Futures",
            "asset_name_cn": "黄金期货",
        }
    ]

    labels = _asset_labels(rows)

    assert labels == ["GC1!|Gold Futures :: 黄金期货（Gold Futures）"]


def test_filter_asset_rows_matches_chinese_name():
    rows = [
        {
            "asset_key": "GC1!|Gold Futures",
            "asset_code": "GC1!",
            "asset_name": "Gold Futures",
            "asset_name_cn": "黄金期货",
            "dataset_type": "core",
            "relative_state": "lead",
        },
        {
            "asset_key": "SI1!|Silver Futures",
            "asset_code": "SI1!",
            "asset_name": "Silver Futures",
            "asset_name_cn": "白银期货",
            "dataset_type": "core",
            "relative_state": "lead",
        },
    ]

    filtered = _filter_asset_rows(rows, "黄金")

    assert [row["asset_code"] for row in filtered] == ["GC1!"]


def test_asset_table_frame_can_be_filtered_by_chinese_futures_name():
    rows = [
        {
            "asset_key": "GC1!|Gold Futures",
            "asset_code": "GC1!",
            "asset_name": "Gold Futures",
            "asset_name_cn": "黄金期货",
            "day_trend": "上行趋势",
        },
        {
            "asset_key": "SI1!|Silver Futures",
            "asset_code": "SI1!",
            "asset_name": "Silver Futures",
            "asset_name_cn": "白银期货",
            "day_trend": "下行趋势",
        },
    ]

    frame = _asset_table_frame(rows, [], [])
    filtered = _filter_asset_frame(frame, "黄金")

    assert list(filtered["asset_code"]) == ["GC1!"]
    assert list(filtered["中文名称"]) == ["黄金期货"]


def test_market_quadrant_figure_uses_chinese_label_when_available():
    rows = [
        {
            "asset_key": "GC1!|Gold Futures",
            "asset_code": "GC1!",
            "asset_name": "Gold Futures",
            "asset_name_cn": "黄金期货",
            "dataset_date": "2026-06-18",
            "day_trend": "上行趋势",
            "relative_strength": 106.0,
            "strength_momentum": 104.0,
            "relative_state": "lead",
        },
    ]

    figure = _market_quadrant_figure(rows, show_labels=True)

    assert list(figure.data[0].text) == ["黄金期货"]
    assert figure.data[0].customdata[0][2] == "黄金期货"

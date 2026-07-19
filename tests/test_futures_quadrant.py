from datetime import date
from pathlib import Path

from asset_tracker.database import AssetDatabase
from asset_tracker.futures_quadrant import (
    classify_futures_group,
    futures_quadrant_figure,
    load_futures_commodity_trajectories,
)
from asset_tracker.domestic_futures import domestic_futures_symbol, is_domestic_commodity_future
from asset_tracker.futures_quadrant_page import render_futures_trajectory_grid
from asset_tracker.parsers import DatasetMetadata, ParsedDataset


def test_classify_futures_group_handles_requested_commodity_groups_and_duplicate_codes():
    assert classify_futures_group({"asset_code": "GC1!", "asset_name_cn": "黄金期货", "asset_name": "Gold Futures"}) == "贵金属"
    assert classify_futures_group({"asset_code": "CU1!", "asset_name_cn": "阴极铜期货", "asset_name": "Copper Cathode Futures"}) == "有色"
    assert classify_futures_group({"asset_code": "PX1!", "asset_name_cn": "对二甲苯期货", "asset_name": "p-Xylene Futures"}) == "化工品"
    assert classify_futures_group({"asset_code": "AP1!", "asset_name_cn": "苹果期货", "asset_name": "Fresh Apple Futures"}) == "农产品"
    assert classify_futures_group({"asset_code": "PL1!", "asset_name_cn": "丙烯期货", "asset_name": "Propylene Futures"}) == "化工品"
    assert classify_futures_group({"asset_code": "PL1!", "asset_name_cn": "铂金期货", "asset_name": "Platinum Futures"}) == "贵金属"
    assert classify_futures_group({"asset_code": "ZN1!", "asset_name_cn": "10年期美债期货", "asset_name": "10-Year T-Note Futures"}) is None


def test_classify_domestic_main_contracts_without_bang_suffix():
    assert classify_futures_group({"asset_code": "AL8", "asset_name": "豆一主连"}) == "农产品"
    assert classify_futures_group({"asset_code": "IL8", "asset_name": "铁矿主连"}) == "黑色建材"
    assert classify_futures_group({"asset_code": "SCL8", "asset_name": "国内原油主连"}) == "能源运输"


def test_domestic_futures_detection_uses_chinese_contract_name_not_code_only():
    assert is_domestic_commodity_future({"asset_code": "TA1!", "asset_name_cn": "PTA期货"}) is True
    assert domestic_futures_symbol({"asset_code": "TA1!", "asset_name_cn": "PTA期货"}) == "TA0.CNFUT"
    assert is_domestic_commodity_future({"asset_code": "RB1!", "asset_name_cn": "RBOB汽油期货"}) is False
    assert domestic_futures_symbol({"asset_code": "RB1!", "asset_name_cn": "RBOB汽油期货"}) is None


def test_load_futures_commodity_trajectories_returns_daily_paths(tmp_path):
    db = AssetDatabase(tmp_path / "signals.sqlite")
    db.initialize()
    _import_rows(
        db,
        date(2026, 6, 9),
        "day1",
        [
            _row("GC1!", "Gold Futures", 95.0, 96.0),
            _row("CU1!", "Copper Cathode Futures", 102.0, 104.0),
            _row("ES1!", "E-mini S&P 500 Futures", 101.0, 103.0),
        ],
    )
    _import_rows(
        db,
        date(2026, 6, 10),
        "day2",
        [
            _row("GC1!", "Gold Futures", 98.0, 99.0),
            _row("CU1!", "Copper Cathode Futures", 104.0, 106.0),
            _row("ES1!", "E-mini S&P 500 Futures", 102.0, 104.0),
        ],
    )

    trajectories = load_futures_commodity_trajectories(db.path, dataset_date="2026-06-10")

    assert [item.asset_code for item in trajectories] == ["CU1!", "GC1!"]
    assert [item.group for item in trajectories] == ["有色", "贵金属"]
    assert [point.date for point in trajectories[1].points] == ["2026-06-09", "2026-06-10"]
    assert [(point.x, point.y) for point in trajectories[1].points] == [(-5.0, -4.0), (-2.0, -1.0)]


def test_futures_quadrant_figure_draws_one_trace_per_futures_asset():
    trajectories = [
        _trajectory("GC1!", "黄金期货", "贵金属", [("2026-06-09", -5.0, -4.0), ("2026-06-10", -2.0, -1.0)]),
        _trajectory("CU1!", "阴极铜期货", "有色", [("2026-06-09", 2.0, 4.0), ("2026-06-10", 4.0, 6.0)]),
    ]

    figure = futures_quadrant_figure(trajectories)

    assert [trace.name for trace in figure.data] == ["阴极铜期货", "黄金期货"]
    assert list(figure.data[1].x) == [-5.0, -2.0]
    assert list(figure.data[1].y) == [-4.0, -1.0]
    assert len([shape for shape in figure.layout.shapes if shape.type == "rect"]) == 4
    assert "Leading" in [annotation.text for annotation in figure.layout.annotations]


def test_render_futures_trajectory_grid_draws_one_chart_per_asset_in_selected_group():
    trajectories = [
        _trajectory("BU1!", "沥青期货", "化工品", [("2026-06-09", -3.0, 2.0), ("2026-06-10", 1.0, 4.0)]),
        _trajectory("GC1!", "黄金期货", "贵金属", [("2026-06-09", -5.0, -4.0), ("2026-06-10", -2.0, -1.0)]),
        _trajectory("CU1!", "阴极铜期货", "有色", [("2026-06-09", 2.0, 4.0), ("2026-06-10", 4.0, 6.0)]),
    ]
    fake_st = _FakeStreamlit()

    render_futures_trajectory_grid(trajectories, selected_group="化工品", st_api=fake_st, columns_per_row=2)

    assert len(fake_st.plotly_calls) == 1
    assert [call["key"] for call in fake_st.plotly_calls] == [
        "futures-commodity-quadrant-BU1",
    ]
    assert [trace.name for trace in fake_st.plotly_calls[0]["figure"].data] == ["沥青期货"]
    assert all(len(call["figure"].data) == 1 for call in fake_st.plotly_calls)

    fake_st = _FakeStreamlit()
    render_futures_trajectory_grid(trajectories, selected_group="贵金属", st_api=fake_st, columns_per_row=2)

    assert len(fake_st.plotly_calls) == 1
    assert [call["key"] for call in fake_st.plotly_calls] == ["futures-commodity-quadrant-GC1"]
    assert [trace.name for trace in fake_st.plotly_calls[0]["figure"].data] == ["黄金期货"]


class _FakeColumn:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def markdown(self, value):
        self.owner.markdowns.append(value)

    def plotly_chart(self, figure, **kwargs):
        self.owner.plotly_calls.append({"figure": figure, **kwargs})


class _FakeStreamlit:
    def __init__(self):
        self.captions = []
        self.markdowns = []
        self.subheaders = []
        self.plotly_calls = []

    def caption(self, value):
        self.captions.append(value)

    def subheader(self, value):
        self.subheaders.append(value)

    def info(self, value):
        self.info_message = value

    def columns(self, count):
        return [_FakeColumn(self) for _ in range(count)]


def _trajectory(asset_code, name_cn, group, points):
    from asset_tracker.analysis import QuadrantPoint, classify_quadrant
    from asset_tracker.futures_quadrant import FuturesTrajectory

    return FuturesTrajectory(
        asset_key=f"{asset_code}|{name_cn}",
        asset_code=asset_code,
        display_name=name_cn,
        group=group,
        points=[
            QuadrantPoint(
                date=day,
                x=x,
                y=y,
                quadrant=classify_quadrant(x, y),
                relative_state="",
                relative_strength=x + 100,
                strength_momentum=y + 100,
            )
            for day, x, y in points
        ],
    )


def _import_rows(db: AssetDatabase, dataset_date: date, source_hash: str, rows: list[dict]) -> None:
    parsed = ParsedDataset(
        metadata=DatasetMetadata(dataset_date, "core"),
        source_path=Path(f"{source_hash}.xlsx"),
        source_hash=source_hash,
        rows=rows,
    )
    db.import_parsed_dataset(parsed, parsed.source_path)


def _row(asset_code: str, asset_name: str, relative_strength: float, strength_momentum: float) -> dict:
    return {
        "asset_code": asset_code,
        "asset_name": asset_name,
        "day_trend": "上行趋势",
        "day_trend_duration": 1,
        "week_trend": "上行趋势",
        "week_trend_duration": 1,
        "month_trend": "上行趋势",
        "month_trend_duration": 1,
        "close_position_60d": 0.7,
        "relative_strength": relative_strength,
        "strength_momentum": strength_momentum,
        "early_turn": 100.0,
        "relative_state_duration": 1,
        "relative_state": "lead",
        "relative_state_return": 1.0,
        "previous_relative_state": "Improving",
        "previous_relative_state_return": 0.5,
        "previous_relative_state_duration": 2,
        "capital_state_duration": 1,
        "capital_state": "加杠杆",
        "capital_state_return": 1.0,
        "previous_capital_state": "去杠杆",
        "previous_capital_state_return": -0.5,
        "capital_value": 80.0,
        "capital_daily_change": 2.0,
    }

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from .analysis import QuadrantPoint, build_quadrant_trajectory
from .asset_names import display_asset_name
from .database import AssetDatabase
from .domestic_futures import domestic_futures_group


REQUESTED_GROUPS = ("化工品", "农产品", "有色", "贵金属", "黑色建材", "能源运输")

FUTURES_GROUP_BY_NAME = {
    "铸造铝合金期货": "有色",
    "白银期货": "贵金属",
    "高级铝期货": "有色",
    "铝期货": "有色",
    "氧化铝期货": "有色",
    "苹果期货": "农产品",
    "黄金期货": "贵金属",
    "丁二烯橡胶期货": "化工品",
    "布伦特原油期货": "化工品",
    "沥青期货": "化工品",
    "A级铜期货": "有色",
    "可可期货": "农产品",
    "棉花期货": "农产品",
    "红枣期货": "农产品",
    "原油期货": "化工品",
    "2号棉花期货": "农产品",
    "阴极铜期货": "有色",
    "棉纱期货": "农产品",
    "玻璃期货": "化工品",
    "燃料油期货": "化工品",
    "育肥牛期货": "农产品",
    "热轧卷板期货": "有色",
    "瘦肉猪期货": "农产品",
    "铜期货": "有色",
    "纽约港超低硫柴油期货": "化工品",
    "JKM日韩液化天然气期货": "化工品",
    "咖啡C期货": "农产品",
    "堪萨斯硬红冬小麦期货": "农产品",
    "木材期货": "农产品",
    "活牛期货": "农产品",
    "甲醇期货": "化工品",
    "亨利港天然气期货": "化工品",
    "镍期货": "有色",
    "菜籽油期货": "农产品",
    "冷冻浓缩橙汁A期货": "农产品",
    "钯金期货": "贵金属",
    "铅期货": "有色",
    "短纤期货": "化工品",
    "花生期货": "农产品",
    "铂金期货": "贵金属",
    "丙烯期货": "化工品",
    "PET瓶片期货": "化工品",
    "对二甲苯期货": "化工品",
    "E-mini 天然气期货": "化工品",
    "RBOB汽油期货": "化工品",
    "罗布斯塔咖啡期货": "农产品",
    "菜粕期货": "农产品",
    "加拿大油菜籽期货": "农产品",
    "油菜籽期货": "农产品",
    "天然橡胶期货": "化工品",
    "纯碱期货": "化工品",
    "11号原糖期货": "农产品",
    "硅铁期货": "有色",
    "烧碱期货": "化工品",
    "锰硅期货": "有色",
    "锡期货": "有色",
    "漂白针叶浆期货": "化工品",
    "白糖期货": "农产品",
    "不锈钢期货": "有色",
    "PTA期货": "化工品",
    "荷兰TTF天然气月度期货": "化工品",
    "尿素期货": "化工品",
    "U3O8铀期货": "有色",
    "线材期货": "有色",
    "玉米期货": "农产品",
    "动力煤期货": "化工品",
    "豆油期货": "农产品",
    "豆粕期货": "农产品",
    "锌期货": "有色",
    "燕麦期货": "农产品",
    "糙米期货": "农产品",
    "大豆期货": "农产品",
    "特级锌期货": "有色",
    "芝加哥软红冬小麦期货": "农产品",
}

GROUP_COLORS = {
    "化工品": "#0969da",
    "贵金属": "#bf8700",
    "有色": "#2da44e",
    "农产品": "#cf222e",
    "黑色建材": "#8250df",
    "能源运输": "#bc4c00",
}


@dataclass(frozen=True)
class FuturesTrajectory:
    asset_key: str
    asset_code: str
    display_name: str
    group: str
    points: list[QuadrantPoint]


def classify_futures_group(row: dict[str, Any]) -> str | None:
    group = domestic_futures_group(row)
    if group:
        return group
    code = str(row.get("asset_code", ""))
    if "!" not in code:
        return None
    name_cn = str(row.get("asset_name_cn") or "").strip()
    if name_cn in FUTURES_GROUP_BY_NAME:
        return FUTURES_GROUP_BY_NAME[name_cn]
    original = str(row.get("asset_name") or "").strip()
    for name, group in FUTURES_GROUP_BY_NAME.items():
        if name and name in original:
            return group
    return None


def load_futures_commodity_trajectories(
    db_path: str | Path,
    dataset_date: str | None = None,
    dataset_type: str | None = "core",
) -> list[FuturesTrajectory]:
    db = AssetDatabase(db_path)
    db.initialize()
    selected_date = dataset_date or db.get_latest_date(dataset_type)
    if not selected_date:
        return []
    rows = db.get_observations_for_date(selected_date, dataset_type)
    latest_by_key = {
        str(row.get("asset_key") or f"{row.get('asset_code')}|{row.get('asset_name')}"): row
        for row in rows
    }
    trajectories: list[FuturesTrajectory] = []
    for asset_key, row in latest_by_key.items():
        group = classify_futures_group(row)
        if group not in REQUESTED_GROUPS:
            continue
        history = db.get_asset_history(asset_key)
        if dataset_type:
            history = [item for item in history if item.get("dataset_type") == dataset_type]
        points = build_quadrant_trajectory(history)
        if not points:
            continue
        trajectories.append(
            FuturesTrajectory(
                asset_key=asset_key,
                asset_code=str(row.get("asset_code") or ""),
                display_name=display_asset_name(row) or str(row.get("asset_name") or row.get("asset_code") or ""),
                group=group,
                points=points,
            )
        )
    return sorted(trajectories, key=lambda item: (REQUESTED_GROUPS.index(item.group), item.display_name, item.asset_key))


def futures_quadrant_figure(
    trajectories: list[FuturesTrajectory],
    *,
    height: int = 760,
    showlegend: bool = True,
) -> go.Figure:
    fig = go.Figure()
    axis_limit = _axis_limit(trajectories)
    _add_quadrant_background(fig, axis_limit)
    for item in sorted(trajectories, key=lambda value: value.display_name):
        color = GROUP_COLORS.get(item.group, "#8c959f")
        fig.add_trace(
            go.Scatter(
                x=[point.x for point in item.points],
                y=[point.y for point in item.points],
                mode="lines+markers+text",
                text=["" for _ in item.points[:-1]] + [item.display_name],
                textposition="top center",
                name=item.display_name,
                legendgroup=item.group,
                marker=dict(size=[7 for _ in item.points[:-1]] + [13], color=color, line=dict(width=1, color="#333")),
                line=dict(color=color, width=2),
                customdata=[
                    [item.group, item.asset_code, item.display_name, point.date, point.quadrant]
                    for point in item.points
                ],
                hovertemplate=(
                    "分组=%{customdata[0]}<br>"
                    "代码=%{customdata[1]}<br>"
                    "品种=%{customdata[2]}<br>"
                    "日期=%{customdata[3]}<br>"
                    "象限=%{customdata[4]}<br>"
                    "相对强度-100=%{x:.2f}<br>"
                    "强度动量-100=%{y:.2f}<extra></extra>"
                ),
            )
        )
    fig.add_hline(y=0, line_dash="dash", line_color="#9a6700", line_width=2)
    fig.add_vline(x=0, line_dash="dash", line_color="#9a6700", line_width=2)
    for text, x, y in [
        ("Improving", 0.07, 0.93),
        ("Leading", 0.93, 0.93),
        ("Lagging", 0.07, 0.07),
        ("Weakening", 0.93, 0.07),
    ]:
        fig.add_annotation(text=text, x=x, y=y, xref="paper", yref="paper", showarrow=False, font=dict(size=14, color="#9a6700"))
    fig.update_layout(
        height=height,
        showlegend=showlegend,
        margin=dict(l=35, r=25, t=20, b=45),
        xaxis_title="相对强度 - 100",
        yaxis_title="强度动量 - 100",
        legend=dict(orientation="v", x=1.01, y=1.0, groupclick="toggleitem"),
    )
    fig.update_xaxes(range=[-axis_limit, axis_limit], zeroline=False)
    fig.update_yaxes(range=[-axis_limit, axis_limit], zeroline=False, scaleanchor="x", scaleratio=1)
    return fig


def _axis_limit(trajectories: list[FuturesTrajectory]) -> float:
    values = []
    for item in trajectories:
        for point in item.points:
            values.extend([abs(point.x), abs(point.y)])
    if not values:
        return 10.0
    return max(10.0, round(max(values) * 1.2, 2))


def _add_quadrant_background(fig: go.Figure, axis_limit: float) -> None:
    quadrants = [
        (0, 0, axis_limit, axis_limit, "rgba(46, 160, 67, 0.08)"),
        (-axis_limit, 0, 0, axis_limit, "rgba(9, 105, 218, 0.08)"),
        (-axis_limit, -axis_limit, 0, 0, "rgba(207, 34, 46, 0.07)"),
        (0, -axis_limit, axis_limit, 0, "rgba(191, 135, 0, 0.08)"),
    ]
    for x0, y0, x1, y1, color in quadrants:
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, fillcolor=color, line_width=0, layer="below")

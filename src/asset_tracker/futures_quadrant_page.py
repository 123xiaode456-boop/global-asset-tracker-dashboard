from __future__ import annotations

from pathlib import Path
import re

import streamlit as st

from .cli import DEFAULT_DB
from .auth import require_access
from .database import AssetDatabase
from .futures_quadrant import FuturesTrajectory, futures_quadrant_figure, load_futures_commodity_trajectories
from .navigation import render_navigation


def run_page(default_db: str | Path = DEFAULT_DB) -> None:
    st.set_page_config(page_title="期货品种四象限", layout="wide")
    if not require_access():
        return
    render_navigation()
    db_path = Path(st.sidebar.text_input("数据库", str(default_db)))
    if not db_path.exists():
        st.warning("数据库尚未创建。请先导入知识星球 Excel。")
        return

    db = AssetDatabase(db_path)
    db.initialize()
    dates = db.list_dataset_dates("core")
    if not dates:
        st.warning("暂无核心数据集日期。")
        return
    selected_date = st.sidebar.selectbox("观察日期", dates, index=len(dates) - 1)
    trajectories = load_futures_commodity_trajectories(db_path, dataset_date=selected_date, dataset_type="core")

    st.title("期货品种四象限位置变化")
    render_futures_trajectory_grid(trajectories)


def render_futures_trajectory_grid(
    trajectories: list[FuturesTrajectory],
    *,
    st_api=st,
    columns_per_row: int = 2,
) -> None:
    if not trajectories:
        st_api.info("当前日期暂无可展示的期货品种四象限轨迹。")
        return

    st_api.caption(f"共 {len(trajectories)} 个期货品种；每个小图展示一个品种在四象限中的位置移动曲线。")
    used_keys: dict[str, int] = {}
    current_group = None
    columns = []
    group_index = 0

    for item in trajectories:
        if item.group != current_group:
            current_group = item.group
            group_index = 0
            st_api.subheader(current_group)
            columns = []

        if group_index % columns_per_row == 0:
            columns = st_api.columns(columns_per_row)
        column = columns[group_index % columns_per_row]
        key = _unique_chart_key(item, used_keys)
        column.markdown(f"**{item.display_name}**  `{item.asset_code}`")
        column.plotly_chart(
            futures_quadrant_figure([item], height=430, showlegend=False),
            width="stretch",
            key=key,
        )
        group_index += 1


def _unique_chart_key(item: FuturesTrajectory, used_keys: dict[str, int]) -> str:
    raw_code = item.asset_code or item.asset_key or item.display_name
    base = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "", raw_code) or "asset"
    prefix = f"futures-commodity-quadrant-{base}"
    used_keys[prefix] = used_keys.get(prefix, 0) + 1
    if used_keys[prefix] == 1:
        return prefix
    return f"{prefix}-{used_keys[prefix]}"

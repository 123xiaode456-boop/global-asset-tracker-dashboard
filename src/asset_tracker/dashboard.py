from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from .analysis import QuadrantPoint, TradeDecision, classify_quadrant, classify_trade_decision
from .asset_names import display_asset_name
from .cli import DEFAULT_DB
from .database import AssetDatabase
from .dashboard_data import get_asset_panel_data, load_dashboard_snapshot, load_price_coverage
from .market_data import build_symbol_mapping_queue
from .navigation import render_futures_entry, render_navigation


RELATIVE_STATE_QUADRANTS = {
    "improving": {"label": "Improving", "x_sign": -1, "y_sign": 1},
    "lead": {"label": "Leading", "x_sign": 1, "y_sign": 1},
    "leading": {"label": "Leading", "x_sign": 1, "y_sign": 1},
    "lag": {"label": "Lagging", "x_sign": -1, "y_sign": -1},
    "lagging": {"label": "Lagging", "x_sign": -1, "y_sign": -1},
    "weakening": {"label": "Weakening", "x_sign": 1, "y_sign": -1},
}

RETURN_DIRECTIONS = {
    "up": {"name": "上涨", "color": "#cf222e"},
    "down": {"name": "下跌", "color": "#1a7f37"},
}
MARKET_QUADRANT_PLOTLY_CONFIG = {"scrollZoom": True, "displayModeBar": True, "displaylogo": False}


def run_app(default_db: str | Path = DEFAULT_DB) -> None:
    st.set_page_config(page_title="全球资产判断系统", layout="wide")
    st.title("全球资产判断系统")
    render_navigation()
    render_futures_entry()

    db_path = Path(st.sidebar.text_input("数据库", str(default_db)))
    if not db_path.exists():
        st.warning("数据库尚未创建。请先运行导入命令。")
        return

    snapshot_all = load_dashboard_snapshot(db_path)
    dataset_options = ["全部", *snapshot_all.dataset_types]
    selected_type = st.sidebar.selectbox("数据集", dataset_options, index=0)
    dataset_type = None if selected_type == "全部" else selected_type
    snapshot_for_dates = load_dashboard_snapshot(db_path, dataset_type)
    date_options = snapshot_for_dates.available_dates
    if not date_options:
        st.warning("数据库中暂无可展示日期。")
        return
    selected_date = st.sidebar.selectbox("观察日期", date_options, index=len(date_options) - 1)
    snapshot = load_dashboard_snapshot(db_path, dataset_type, selected_date)

    cols = st.columns(5)
    cols[0].metric("日期", snapshot.latest_date or "-")
    cols[1].metric("标的", snapshot.latest_counts.get("total", 0))
    cols[2].metric("加杠杆", snapshot.latest_counts.get("capital_add", 0))
    cols[3].metric("去杠杆", snapshot.latest_counts.get("capital_reduce", 0))
    cols[4].metric("重点观察", len(snapshot.focus_watch))

    tab_overview, tab_table, tab_quadrant, tab_asset, tab_unmapped = st.tabs(
        ["总览", "资产表", "四象限", "单资产", "待映射"]
    )

    with tab_overview:
        st.subheader("当日机会推荐排名")
        long_rank, short_rank = st.columns(2)
        with long_rank:
            st.caption("做多候选：日趋势上行 + 比价/资金/周期共振越强越靠前")
            st.dataframe(_frame(snapshot.long_opportunities), width="stretch", height=300, hide_index=True)
        with short_rank:
            st.caption("做空/风险候选：日趋势下行 + 弱势/去杠杆共振越强越靠前")
            st.dataframe(_frame(snapshot.short_opportunities), width="stretch", height=300, hide_index=True)

        left, right = st.columns(2)
        with left:
            st.subheader("重点观察")
            st.dataframe(_frame(snapshot.focus_watch), width="stretch", height=360)
        with right:
            st.subheader("风险观察")
            st.dataframe(_frame(snapshot.risk_watch), width="stretch", height=360)

    with tab_table:
        frame = _asset_table_frame(snapshot.latest_rows, snapshot.long_opportunities, snapshot.short_opportunities)
        search = st.text_input("搜索代码/中文/英文名称")
        frame = _filter_asset_frame(frame, search)
        st.dataframe(frame, width="stretch", height=620)

    with tab_quadrant:
        assets = _unique_asset_rows(snapshot.latest_rows)
        st.subheader("全市场四象限分布")
        if not assets:
            st.info("暂无资产。")
        else:
            quadrant_search = st.text_input("筛选四象限代码/中文/英文名称")
            quadrant_rows = _filter_asset_rows(assets, quadrant_search)
            show_labels = st.checkbox("显示名称标签", value=False)
            st.plotly_chart(
                _market_quadrant_figure(quadrant_rows, show_labels=show_labels),
                width="stretch",
                key="market-quadrant-map",
                config=MARKET_QUADRANT_PLOTLY_CONFIG,
            )
            st.dataframe(
                _market_quadrant_table(quadrant_rows),
                width="stretch",
                height=260,
                hide_index=True,
            )

            st.subheader("当日机会排名")
            q_long_rank, q_short_rank = st.columns(2)
            with q_long_rank:
                st.caption("做多候选")
                st.dataframe(_frame(snapshot.long_opportunities), width="stretch", height=260, hide_index=True)
            with q_short_rank:
                st.caption("做空/风险候选")
                st.dataframe(_frame(snapshot.short_opportunities), width="stretch", height=260, hide_index=True)

            st.subheader("单品种象限轨迹")
            labels = _asset_labels(quadrant_rows or assets)
            selected = st.selectbox("轨迹标的", labels)
            asset_code = selected.split(" :: ", 1)[0]
            panel = get_asset_panel_data(db_path, asset_code, dataset_date=selected_date, dataset_type=dataset_type)
            _decision_card(panel.trade_decision, panel.latest_signal)
            _opportunity_card(panel.opportunity)
            q_left, q_right = st.columns([1, 1])
            with q_left:
                st.plotly_chart(
                    _quadrant_figure(panel.quadrant_trajectory),
                    width="stretch",
                    key="quadrant-tab-asset-map",
                )
            with q_right:
                st.plotly_chart(
                    _quadrant_timeline_figure(panel.quadrant_trajectory),
                    width="stretch",
                    key="quadrant-tab-asset-timeline",
                )

    with tab_asset:
        assets = _unique_asset_rows(snapshot.latest_rows)
        if not assets:
            st.info("暂无资产。")
        else:
            asset_search = st.text_input("检索单资产代码/中文/英文名称")
            selected_assets = _filter_asset_rows(assets, asset_search)
            if not selected_assets:
                st.warning("没有找到匹配的资产，请换一个代码、中文名或英文名。")
                return
            labels = _asset_labels(selected_assets)
            selected = st.selectbox("资产", labels)
            asset_code = selected.split(" :: ", 1)[0]
            panel = get_asset_panel_data(db_path, asset_code, dataset_date=selected_date, dataset_type=dataset_type)
            _decision_card(panel.trade_decision, panel.latest_signal)
            _opportunity_card(panel.opportunity)
            st.subheader("行情与指标对比")
            st.plotly_chart(
                _asset_figure(panel.signal_history, panel.price_history),
                width="stretch",
                key="single-asset-price-indicators",
            )
            if panel.unmapped_price:
                st.info("该资产暂无行情映射或价格缓存，当前仅展示星球指标。")
            st.subheader("四象限位置变化")
            q_left, q_right = st.columns([1, 1])
            with q_left:
                st.plotly_chart(
                    _quadrant_figure(panel.quadrant_trajectory),
                    width="stretch",
                    key="single-asset-quadrant-map",
                )
            with q_right:
                st.plotly_chart(
                    _quadrant_timeline_figure(panel.quadrant_trajectory),
                    width="stretch",
                    key="single-asset-quadrant-timeline",
                )
            st.subheader("历史明细")
            st.dataframe(_frame(panel.signal_history), width="stretch", height=360)

    with tab_unmapped:
        coverage = load_price_coverage(db_path, dataset_type, selected_date)
        st.subheader("行情覆盖")
        coverage_cols = st.columns(4)
        coverage_cols[0].metric("最新日期", coverage.latest_date or "-")
        coverage_cols[1].metric("唯一标的", coverage.total_assets)
        coverage_cols[2].metric("已有行情", coverage.assets_with_price)
        coverage_cols[3].metric("缺行情", coverage.assets_without_price, f"{coverage.coverage_ratio:.1%}")
        st.subheader("缺行情资产")
        missing_frame = _frame(coverage.missing_rows)
        missing_search = st.text_input("筛选缺行情代码/中文/英文名称")
        missing_frame = _filter_asset_frame(missing_frame, missing_search)
        st.dataframe(missing_frame, width="stretch", height=360)

        st.subheader("待补中文名资产")
        untranslated_rows = AssetDatabase(db_path).list_untranslated_asset_names()
        st.dataframe(_frame(untranslated_rows), width="stretch", height=320, hide_index=True)

        st.subheader("无法自动猜行情源的资产")
        existing_map = {row["asset_code"]: row for row in AssetDatabase(db_path).list_symbol_mappings()}
        rows = build_symbol_mapping_queue(snapshot.latest_rows, existing_map=existing_map)
        mapping_search = st.text_input("筛选待映射代码/中文/英文名称")
        rows = _filter_asset_rows(rows, mapping_search)
        st.dataframe(_frame(rows), width="stretch", height=620)


def _asset_figure(signal_history: list[dict[str, Any]], price_history: list[dict[str, Any]]) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.45, 0.55],
        subplot_titles=("价格行情", "星球指标"),
    )
    if price_history:
        prices = pd.DataFrame(price_history)
        fig.add_trace(
            go.Scatter(
                x=prices["bar_date"],
                y=prices["close"],
                name="收盘价",
                mode="lines",
            ),
            row=1,
            col=1,
        )
    if signal_history:
        signals = pd.DataFrame(signal_history)
        x = signals["dataset_date"]
        for column, label in [
            ("relative_strength", "相对强度"),
            ("strength_momentum", "强度动量"),
            ("early_turn", "早期转折"),
            ("capital_value", "杠杆资金"),
        ]:
            if column in signals:
                fig.add_trace(
                    go.Scatter(x=x, y=signals[column], name=label, mode="lines+markers"),
                    row=2,
                    col=1,
                )
        _add_state_backgrounds(fig, signals)
    fig.update_layout(
        height=520,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h"),
    )
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="指标", row=2, col=1)
    return fig


def _decision_card(decision: TradeDecision, latest_signal: dict[str, Any] | None) -> None:
    signal = latest_signal or {}
    st.markdown(
        f"""
        <div style="border-left: 6px solid {decision.color}; padding: 14px 18px; background: rgba(127,127,127,0.08); border-radius: 8px; margin: 8px 0 16px 0;">
          <div style="font-size: 14px; color: #777;">当天结论</div>
          <div style="font-size: 30px; font-weight: 700; color: {decision.color};">{decision.label}</div>
          <div style="font-size: 14px; margin-top: 4px;">{decision.reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(6)
    cols[0].metric("日级别趋势", _metric_text(signal.get("day_trend")))
    cols[1].metric("周级别趋势", _metric_text(signal.get("week_trend")))
    cols[2].metric("月级别趋势", _metric_text(signal.get("month_trend")))
    cols[3].metric("比价状态", _metric_text(signal.get("relative_state")))
    cols[4].metric("资金状态", _metric_text(signal.get("capital_state")))
    cols[5].metric("数据日期", _metric_text(signal.get("dataset_date")))


def _opportunity_card(opportunity: dict[str, Any] | None) -> None:
    if not opportunity:
        st.info("该资产在所选日期暂无可用机会解释。")
        return
    rank = opportunity.get("rank")
    rank_text = f"第 {rank} 名" if rank else "未进入机会榜"
    score = opportunity.get("score")
    score_text = "-" if score in (None, "") else f"{float(score):.2f}"
    st.markdown(
        f"""
        <div style="padding: 12px 16px; background: rgba(127,127,127,0.06); border-radius: 8px; margin: 0 0 16px 0;">
          <div style="font-size: 14px; color: #777;">所选日期机会解读</div>
          <div style="font-size: 18px; font-weight: 700;">{opportunity.get("decision_label", "-")} · {rank_text} · 评分 {score_text}</div>
          <div style="font-size: 14px; margin-top: 4px;">{opportunity.get("reasons", "-")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _quadrant_figure(points: list[QuadrantPoint]) -> go.Figure:
    fig = go.Figure()
    axis_limit = _quadrant_axis_limit(points)
    _add_quadrant_background(fig, axis_limit)
    if points:
        fig.add_trace(
            go.Scatter(
                x=[point.x for point in points],
                y=[point.y for point in points],
                mode="lines+markers+text",
                text=[point.date for point in points],
                textposition="top center",
                name="象限轨迹",
                marker=dict(
                    size=[9 if index < len(points) - 1 else 15 for index, _ in enumerate(points)],
                    color=[_quadrant_color(point.quadrant) for point in points],
                    line=dict(width=1, color="#222"),
                ),
                customdata=[
                    [point.date, point.quadrant, point.relative_strength, point.strength_momentum]
                    for point in points
                ],
                hovertemplate=(
                    "日期=%{customdata[0]}<br>"
                    "象限=%{customdata[1]}<br>"
                    "RS-100=%{x:.2f}<br>"
                    "动量-100=%{y:.2f}<br>"
                    "相对强度=%{customdata[2]:.2f}<br>"
                    "强度动量=%{customdata[3]:.2f}<extra></extra>"
                ),
            )
        )
    fig.add_hline(y=0, line_dash="dash", line_color="#9a6700")
    fig.add_vline(x=0, line_dash="dash", line_color="#9a6700")
    for text, x, y in [
        ("Improving", 0.06, 0.94),
        ("Leading", 0.94, 0.94),
        ("Lagging", 0.06, 0.06),
        ("Weakening", 0.94, 0.06),
    ]:
        fig.add_annotation(
            text=text,
            x=x,
            y=y,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=13, color="#9a6700"),
        )
    fig.update_layout(
        height=500,
        margin=dict(l=30, r=20, t=25, b=35),
        xaxis_title="相对强度（按当日基准居中）",
        yaxis_title="强度动量（按当日基准居中）",
        legend=dict(orientation="h"),
    )
    fig.update_xaxes(range=[-axis_limit, axis_limit], zeroline=False)
    fig.update_yaxes(range=[-axis_limit, axis_limit], zeroline=False, scaleanchor="x", scaleratio=1)
    return fig


def _market_quadrant_figure(rows: list[dict[str, Any]], show_labels: bool = False) -> go.Figure:
    fig = go.Figure()
    plotted_points = []
    for row in rows:
        point = _relative_state_market_point(row)
        if point is None:
            continue
        plotted_points.append((row, point))

    x_axis = _mirrored_axis([abs(point["x"]) for _, point in plotted_points], min_outer=1.0)
    y_axis = _mirrored_axis([abs(point["y"]) for _, point in plotted_points], min_outer=1.0)
    _add_quadrant_background_xy(fig, x_axis["outer"], y_axis["outer"])
    grouped: dict[str, dict[str, Any]] = {
        direction: {"name": config["name"], "color": config["color"], "x": [], "y": [], "text": [], "customdata": []}
        for direction, config in RETURN_DIRECTIONS.items()
    }
    for row, point in plotted_points:
        group = grouped[point["direction"]]
        group["x"].append(point["x"])
        group["y"].append(point["y"])
        display_name = display_asset_name(row)
        group["text"].append(display_name or str(row.get("asset_name") or row.get("asset_code") or ""))
        group["customdata"].append(
            [
                row.get("dataset_date"),
                row.get("asset_code"),
                display_name or row.get("asset_name"),
                row.get("asset_name"),
                row.get("relative_state"),
                point["quadrant"],
                point["duration"],
                point["return_value"],
                group["name"],
            ]
        )
    mode = "markers+text" if show_labels else "markers"
    textposition = "top center" if show_labels else None
    for group in grouped.values():
        fig.add_trace(
            go.Scatter(
                x=group["x"],
                y=group["y"],
                mode=mode,
                text=group["text"],
                textposition=textposition,
                name=group["name"],
                marker=dict(size=10, color=group["color"], opacity=0.78, line=dict(width=1, color="#202020")),
                customdata=group["customdata"],
                hovertemplate=(
                    "日期=%{customdata[0]}<br>"
                    "代码=%{customdata[1]}<br>"
                    "中文名称=%{customdata[2]}<br>"
                    "原始名称=%{customdata[3]}<br>"
                    "比价状态=%{customdata[4]}<br>"
                    "象限=%{customdata[5]}<br>"
                    "持续时间=%{customdata[6]}<br>"
                    "涨跌幅=%{customdata[7]:.2f}<br>"
                    "方向=%{customdata[8]}<extra></extra>"
                ),
            )
        )
    fig.add_hline(y=0, line_dash="dash", line_color="#9a6700")
    fig.add_vline(x=0, line_dash="dash", line_color="#9a6700")
    for text, x, y in [
        ("Improving", 0.06, 0.94),
        ("Leading", 0.94, 0.94),
        ("Lagging", 0.06, 0.06),
        ("Weakening", 0.94, 0.06),
    ]:
        fig.add_annotation(
            text=text,
            x=x,
            y=y,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=13, color="#9a6700"),
        )
    fig.update_layout(
        height=620,
        margin=dict(l=30, r=20, t=25, b=35),
        xaxis_title="当前比价状态持续时间（左右均为正值）",
        yaxis_title="当前比价状态涨跌幅绝对值（上下均为正值）",
        legend=dict(orientation="h"),
        dragmode="pan",
    )
    fig.update_xaxes(
        range=[-x_axis["outer"], x_axis["outer"]],
        tickvals=x_axis["tickvals"],
        ticktext=x_axis["ticktext"],
        zeroline=False,
    )
    fig.update_yaxes(
        range=[-y_axis["outer"], y_axis["outer"]],
        tickvals=y_axis["tickvals"],
        ticktext=y_axis["ticktext"],
        zeroline=False,
    )
    return fig


def _relative_state_market_point(row: dict[str, Any]) -> dict[str, Any] | None:
    state = str(row.get("relative_state") or "").strip().lower()
    config = RELATIVE_STATE_QUADRANTS.get(state)
    duration = _to_float(row.get("relative_state_duration"))
    return_value = _to_float(row.get("relative_state_return"))
    if config is None or duration is None or return_value is None:
        return None
    return {
        "x": config["x_sign"] * abs(duration),
        "y": config["y_sign"] * abs(return_value),
        "direction": "up" if return_value >= 0 else "down",
        "quadrant": config["label"],
        "duration": abs(duration),
        "return_value": return_value,
    }


def _mirrored_axis(values: list[float], *, min_outer: float) -> dict[str, Any]:
    outer = _nice_axis_outer(max([abs(value) for value in values] + [min_outer]))
    middle = _nice_axis_tick(outer / 2)
    return {
        "outer": outer,
        "tickvals": [-outer, -middle, 0, middle, outer],
        "ticktext": [_format_tick(outer), _format_tick(middle), "0", _format_tick(middle), _format_tick(outer)],
    }


def _nice_axis_outer(value: float) -> float:
    if value <= 0:
        return 1.0
    return _nice_axis_tick(value * 1.15)


def _nice_axis_tick(value: float) -> float:
    if value >= 20:
        return float(int((value + 4) // 5 * 5))
    if value >= 5:
        return float(int(value + 0.999999))
    if value >= 1:
        return float(int(value * 2 + 0.999999) / 2)
    return float(int(value * 10 + 0.999999) / 10)


def _format_tick(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _add_quadrant_background(fig: go.Figure, axis_limit: float) -> None:
    _add_quadrant_background_xy(fig, axis_limit, axis_limit)


def _add_quadrant_background_xy(fig: go.Figure, x_axis_limit: float, y_axis_limit: float) -> None:
    quadrants = [
        (0, 0, x_axis_limit, y_axis_limit, "rgba(46, 160, 67, 0.08)"),
        (-x_axis_limit, 0, 0, y_axis_limit, "rgba(9, 105, 218, 0.08)"),
        (-x_axis_limit, -y_axis_limit, 0, 0, "rgba(207, 34, 46, 0.07)"),
        (0, -y_axis_limit, x_axis_limit, 0, "rgba(191, 135, 0, 0.08)"),
    ]
    for x0, y0, x1, y1, color in quadrants:
        fig.add_shape(
            type="rect",
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            fillcolor=color,
            line_width=0,
            layer="below",
        )


def _quadrant_axis_limit(points: list[QuadrantPoint]) -> float:
    if not points:
        return 10.0
    max_abs = max(max(abs(point.x), abs(point.y)) for point in points)
    return max(10.0, round(max_abs * 1.2, 2))


def _market_axis_limit(rows: list[dict[str, Any]]) -> float:
    values = []
    for row in rows:
        relative_strength = _to_float(row.get("relative_strength"))
        strength_momentum = _to_float(row.get("strength_momentum"))
        if relative_strength is None or strength_momentum is None:
            continue
        values.extend([abs(relative_strength - 100.0), abs(strength_momentum - 100.0)])
    if not values:
        return 10.0
    return max(10.0, round(max(values) * 1.2, 2))


def _quadrant_timeline_figure(points: list[QuadrantPoint]) -> go.Figure:
    fig = go.Figure()
    dates = [point.date for point in points]
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[point.x for point in points],
            mode="lines+markers",
            name="横轴坐标（当日居中）",
            marker=dict(color="#0969da"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[point.y for point in points],
            mode="lines+markers",
            name="纵轴坐标（当日居中）",
            marker=dict(color="#2da44e"),
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#9a6700")
    fig.update_layout(
        height=500,
        margin=dict(l=30, r=20, t=25, b=35),
        xaxis_title="日期",
        yaxis_title="象限坐标",
        legend=dict(orientation="h"),
    )
    return fig


def _add_state_backgrounds(fig: go.Figure, signals: pd.DataFrame) -> None:
    if "dataset_date" not in signals or len(signals) == 0:
        return
    colors = {
        "lead": "rgba(46, 160, 67, 0.10)",
        "improving": "rgba(9, 105, 218, 0.10)",
        "weakening": "rgba(251, 188, 4, 0.12)",
        "lag": "rgba(218, 54, 51, 0.10)",
    }
    for _, row in signals.iterrows():
        state = str(row.get("relative_state", "")).lower()
        color = colors.get(state)
        if not color:
            continue
        fig.add_vrect(
            x0=row["dataset_date"],
            x1=row["dataset_date"],
            fillcolor=color,
            line_width=2,
            row=2,
            col=1,
        )


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _filter_asset_frame(frame: pd.DataFrame, search: str) -> pd.DataFrame:
    query = str(search or "").strip()
    if not query or frame.empty:
        return frame
    searchable_columns = [
        "asset_key",
        "asset_code",
        "asset_name",
        "asset_name_cn",
        "中文名称",
        "原始名称",
        "candidate_symbols",
        "reason",
    ]
    mask = pd.Series(False, index=frame.index)
    for column in searchable_columns:
        if column in frame.columns:
            mask = mask | frame[column].astype(str).str.contains(query, case=False, na=False, regex=False)
    return frame[mask]


def _asset_table_frame(
    rows: list[dict[str, Any]],
    long_opportunities: list[dict[str, Any]],
    short_opportunities: list[dict[str, Any]],
) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    opportunity_by_key = {}
    for item in [*long_opportunities, *short_opportunities]:
        if item.get("asset_key"):
            opportunity_by_key[str(item["asset_key"])] = item
        if item.get("asset_code"):
            opportunity_by_key[str(item["asset_code"])] = item
    enriched = []
    for row in rows:
        asset_key = str(row.get("asset_key") or "")
        asset_code = str(row.get("asset_code") or "")
        opportunity = opportunity_by_key.get(asset_key) or opportunity_by_key.get(asset_code)
        decision = classify_trade_decision(row)
        enriched.append(
            {
                "机会排名": opportunity.get("rank") if opportunity else None,
                "机会评分": opportunity.get("score") if opportunity else None,
                "当天结论": decision.label,
                "机会类型": opportunity.get("opportunity_type") if opportunity else "观望",
                "机会原因": opportunity.get("reasons") if opportunity else decision.reason,
                "中文名称": display_asset_name(row),
                "原始名称": row.get("asset_name"),
                **row,
            }
        )
    return pd.DataFrame(enriched)


def _asset_labels(rows: list[dict[str, Any]]) -> list[str]:
    return [
        f"{row.get('asset_key', row['asset_code'])} :: {display_asset_name(row, include_original=True)}"
        for row in rows
    ]


def _filter_asset_rows(rows: list[dict[str, Any]], search: str) -> list[dict[str, Any]]:
    query = search.strip().lower()
    if not query:
        return rows
    filtered = []
    for row in rows:
        haystack = " ".join(
            str(row.get(column, ""))
            for column in ["asset_key", "asset_code", "asset_name", "asset_name_cn", "dataset_type", "relative_state"]
        ).lower()
        if query in haystack:
            filtered.append(row)
    return filtered


def _market_quadrant_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    table_rows = []
    for row in rows:
        relative_strength = _to_float(row.get("relative_strength"))
        strength_momentum = _to_float(row.get("strength_momentum"))
        if relative_strength is None or strength_momentum is None:
            continue
        x = round(relative_strength - 100.0, 6)
        y = round(strength_momentum - 100.0, 6)
        decision = classify_trade_decision(row)
        table_rows.append(
            {
                "日期": row.get("dataset_date"),
                "代码": row.get("asset_code"),
                "中文名称": display_asset_name(row),
                "原始名称": row.get("asset_name"),
                "当天结论": decision.label,
                "日趋势": row.get("day_trend"),
                "象限": classify_quadrant(x, y),
                "RS-100": x,
                "动量-100": y,
                "比价状态": row.get("relative_state"),
                "资金状态": row.get("capital_state"),
            }
        )
    return pd.DataFrame(table_rows)


def _unique_asset_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"core": 2, "betting": 1}
    by_key: dict[str, tuple[int, int, dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = row.get("asset_key") or f"{row.get('asset_code', '')}|{row.get('asset_name', '')}"
        row_priority = priority.get(str(row.get("dataset_type", "")), 0)
        current = by_key.get(str(key))
        if current is None or (row_priority, -index) > (current[0], current[1]):
            by_key[str(key)] = (row_priority, -index, row)
    return [entry[2] for key, entry in sorted(by_key.items(), key=lambda item: item[0])]


def _metric_text(value: Any) -> str:
    return "-" if value in (None, "") else str(value)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quadrant_color(quadrant: str) -> str:
    return {
        "Leading": "#2da44e",
        "Improving": "#57ab5a",
        "Weakening": "#bf8700",
        "Lagging": "#cf222e",
    }.get(quadrant, "#8c959f")

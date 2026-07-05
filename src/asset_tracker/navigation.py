from __future__ import annotations

import streamlit as st


FUTURES_PAGE_PATH = "/期货品种四象限"


def render_navigation() -> None:
    st.sidebar.markdown("### 页面导航")
    st.sidebar.markdown(f"[主仪表盘](/)")
    st.sidebar.markdown(f"[期货品种四象限]({FUTURES_PAGE_PATH})")


def render_futures_entry() -> None:
    st.markdown(f"**快速入口：** [期货品种四象限]({FUTURES_PAGE_PATH})")

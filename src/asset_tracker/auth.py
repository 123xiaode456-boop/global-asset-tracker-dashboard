from __future__ import annotations

import os
from hmac import compare_digest
from typing import Any

import streamlit as st


def require_access(st_api: Any = st) -> bool:
    password = _configured_password(st_api)
    if not password:
        return True

    if st_api.session_state.get("asset_tracker_authenticated"):
        return True

    st_api.title("全球资产判断系统")
    entered = st_api.text_input("访问密码", type="password")
    if not entered:
        st_api.stop()

    if compare_digest(str(entered), str(password)):
        st_api.session_state["asset_tracker_authenticated"] = True
        st_api.rerun()

    st_api.error("密码错误。")
    st_api.stop()
    return False


def _configured_password(st_api: Any) -> str:
    env_password = os.environ.get("ASSET_TRACKER_PASSWORD", "").strip()
    if env_password:
        return env_password
    try:
        return str(st_api.secrets.get("ASSET_TRACKER_PASSWORD", "")).strip()
    except Exception:
        return ""

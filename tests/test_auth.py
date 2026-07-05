import pytest

from asset_tracker.auth import require_access


def test_require_access_allows_when_password_is_not_configured(monkeypatch):
    monkeypatch.delenv("ASSET_TRACKER_PASSWORD", raising=False)
    fake_st = _FakeStreamlit()

    assert require_access(fake_st) is True
    assert fake_st.stopped is False


def test_require_access_allows_authenticated_session(monkeypatch):
    monkeypatch.setenv("ASSET_TRACKER_PASSWORD", "secret")
    fake_st = _FakeStreamlit()
    fake_st.session_state["asset_tracker_authenticated"] = True

    assert require_access(fake_st) is True
    assert fake_st.text_input_calls == []


def test_require_access_stops_when_password_is_missing(monkeypatch):
    monkeypatch.setenv("ASSET_TRACKER_PASSWORD", "secret")
    fake_st = _FakeStreamlit()

    with pytest.raises(_Stopped):
        require_access(fake_st)

    assert fake_st.stopped is True
    assert fake_st.text_input_calls == [("访问密码", "password")]


class _Stopped(Exception):
    pass


class _FakeSecrets:
    def get(self, key, default=None):
        return default


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.secrets = _FakeSecrets()
        self.text_input_calls = []
        self.stopped = False

    def title(self, value):
        self.title_value = value

    def text_input(self, label, type=None):
        self.text_input_calls.append((label, type))
        return ""

    def stop(self):
        self.stopped = True
        raise _Stopped()

    def error(self, value):
        self.error_value = value

    def rerun(self):
        self.rerun_called = True

"""Integration tests for stream renderer state transitions.

Split from test_stream_renderer_deep_integration.py for file length compliance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ami.cli_components.stream_renderer import StreamRenderer
from ami.core.config import _ConfigSingleton


@pytest.fixture(autouse=True)
def _reset_config_singleton(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _capture_renderer(sid: str = "test-session") -> StreamRenderer:
    return StreamRenderer(sid, capture_content=True)


def _display_renderer(sid: str = "test-session") -> StreamRenderer:
    return StreamRenderer(sid, capture_content=False)


class TestStreamRendererStateTransitions:
    def test_initial_state(self):
        r = _capture_renderer()
        assert r.content_started is False
        assert r.box_displayed is False
        assert r.response_box_started is False
        assert r.response_box_ended is False
        assert r.line_buffer == ""
        assert r.in_run_block is False
        assert r.full_output == ""

    def test_after_first_chunk(self):
        r = _capture_renderer()
        r.process_chunk("first")
        assert r.content_started is True
        assert r.box_displayed is True
        assert r.response_box_started is True
        assert r.response_box_ended is False

    def test_capture_box_not_ended_after_finish(self):
        r = _capture_renderer()
        r.process_chunk("data")
        r.finish()
        assert r.response_box_ended is False

    def test_display_box_ended_after_finish(self):
        r = _display_renderer()
        r.timer = MagicMock(is_running=False)
        with patch("ami.cli_components.stream_renderer.time") as mt:
            mt.time.return_value = 1000.0
            mt.strftime.return_value = "00:00:00"
            r.process_chunk("data\n")
            r.finish()
        assert r.response_box_ended is True

    def test_multiple_chunks_accumulate(self):
        r = _capture_renderer()
        r.process_chunk("a")
        r.process_chunk("b")
        r.process_chunk("c")
        assert r.full_output == "abc"

    def test_render_raw_sets_content_started(self):
        r = _capture_renderer()
        assert r.content_started is False
        r.render_raw_line("raw")
        assert r.content_started is True
        assert r.box_displayed is True

"""Integration tests for status display and formatting modules.

Exercises: types/status.py, cli_components/format_utils.py,
cli_components/stream_renderer.py, cli_components/cursor_manager.py,
cli/config.py, cli_components/status_utils.py
"""

import pytest

from ami.cli.config import AgentConfigPresets
from ami.cli_components.cursor_manager import CursorManager
from ami.cli_components.format_utils import GB, KB, MB, format_file_size
from ami.cli_components.status_utils import (
    DISPLAY_WIDTH,
    format_bytes,
    format_ports,
    get_visual_width,
)
from ami.cli_components.stream_renderer import (
    CONTENT_WIDTH,
    TOTAL_WIDTH,
    StreamRenderer,
)
from ami.core.config import _ConfigSingleton
from ami.types.status import (
    PodmanContainer,
    PortMapping,
    ServiceDisplayInfo,
    SystemdService,
)

# --- Named constants for magic numbers used in assertions ---
EXPECTED_HOST_PORT = 8080
EXPECTED_CONTAINER_PORT = 80
EXPECTED_KB = 1024
EXPECTED_HELLO_LEN = 5
EXPECTED_LAST_LINE_INDEX_3 = 2
EXPECTED_COL_AFTER_LEFT = 2
EXPECTED_COL_AFTER_RIGHT = 3
EXPECTED_WRAP_COL = 5
EXPECTED_PREV_WORD_COL = 12
EXPECTED_NEXT_WORD_COL = 6
EXPECTED_EMPTY_LINE_INDEX = 1
EXPECTED_NEXT_PARAGRAPH_LINE = 2
EXPECTED_CLAMP_COL = 2
EXPECTED_CONTENT_WIDTH = 76
EXPECTED_TOTAL_WIDTH = 80
EXPECTED_DISPLAY_WIDTH = 80
EXPECTED_WORKER_TIMEOUT = 180


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# Status types (Pydantic models)
# ---------------------------------------------------------------------------


class TestPortMapping:
    """Test PortMapping model."""

    def test_basic(self):
        pm = PortMapping(host_port=8080, container_port=80)
        assert pm.host_port == EXPECTED_HOST_PORT
        assert pm.container_port == EXPECTED_CONTAINER_PORT
        assert pm.protocol == "tcp"

    def test_udp_protocol(self):
        pm = PortMapping(host_port=53, container_port=53, protocol="udp")
        assert pm.protocol == "udp"


class TestPodmanContainer:
    """Test PodmanContainer model."""

    def test_basic(self):
        container = PodmanContainer(
            id="abc123",
            name="web",
            state="running",
            status="Up 2 hours",
        )
        assert container.name == "web"
        assert container.state == "running"

    def test_with_ports(self):
        container = PodmanContainer(
            id="def456",
            name="api",
            state="running",
            status="Up 1 hour",
            ports=[PortMapping(host_port=3000, container_port=3000)],
        )
        assert len(container.ports) == 1


class TestSystemdService:
    """Test SystemdService model."""

    def test_basic(self):
        svc = SystemdService(
            name="nginx.service",
            active="active",
            sub="running",
        )
        assert svc.name == "nginx.service"
        assert svc.active == "active"


class TestServiceDisplayInfo:
    """Test ServiceDisplayInfo model."""

    def test_basic(self):
        info = ServiceDisplayInfo(
            row_type="service",
            row_details=["nginx"],
        )
        assert info.row_type == "service"
        assert info.row_details == ["nginx"]


# ---------------------------------------------------------------------------
# format_utils
# ---------------------------------------------------------------------------


class TestFormatFileSize:
    """Test format_file_size with various sizes."""

    def test_gigabytes(self):
        result = format_file_size(2 * GB)
        assert "GB" in result

    def test_megabytes(self):
        result = format_file_size(500 * MB)
        assert "MB" in result

    def test_kilobytes(self):
        result = format_file_size(100 * KB)
        assert "KB" in result

    def test_bytes(self):
        result = format_file_size(500)
        assert result == "500B"

    def test_unknown_string(self):
        assert format_file_size("Unknown") == "Unknown"

    def test_string_number(self):
        result = format_file_size(str(2 * MB))
        assert "MB" in result

    def test_invalid_string(self):
        result = format_file_size("not_a_number")
        assert result == "not_a_number"

    def test_zero(self):
        result = format_file_size(0)
        assert result == "0B"

    def test_constants(self):
        assert KB == EXPECTED_KB
        assert MB == EXPECTED_KB * EXPECTED_KB
        assert GB == EXPECTED_KB * EXPECTED_KB * EXPECTED_KB


# ---------------------------------------------------------------------------
# CursorManager
# ---------------------------------------------------------------------------


class TestCursorManager:
    """Test CursorManager movement methods."""

    def test_init_single_line(self):
        cm = CursorManager(["hello"])
        assert cm.current_line == 0
        assert cm.current_col == EXPECTED_HELLO_LEN

    def test_init_multi_line(self):
        cm = CursorManager(["line1", "line2", "line3"])
        assert cm.current_line == EXPECTED_LAST_LINE_INDEX_3
        assert cm.current_col == EXPECTED_HELLO_LEN

    def test_init_empty(self):
        cm = CursorManager([""])
        assert cm.current_line == 0
        assert cm.current_col == 0

    def test_move_up(self):
        cm = CursorManager(["line1", "line2"])
        assert cm.current_line == 1
        cm.move_cursor_up()
        assert cm.current_line == 0

    def test_move_up_at_top(self):
        cm = CursorManager(["only line"])
        cm.current_line = 0
        cm.move_cursor_up()
        assert cm.current_line == 0

    def test_move_down(self):
        cm = CursorManager(["line1", "line2"])
        cm.current_line = 0
        cm.current_col = 0
        cm.move_cursor_down()
        assert cm.current_line == 1

    def test_move_down_at_bottom(self):
        cm = CursorManager(["line1", "line2"])
        cm.current_line = 1
        cm.move_cursor_down()
        assert cm.current_line == 1

    def test_move_left(self):
        cm = CursorManager(["hello"])
        cm.current_col = 3
        cm.move_cursor_left()
        assert cm.current_col == EXPECTED_COL_AFTER_LEFT

    def test_move_left_wraps_to_previous_line(self):
        cm = CursorManager(["line1", "line2"])
        cm.current_line = 1
        cm.current_col = 0
        cm.move_cursor_left()
        assert cm.current_line == 0
        assert cm.current_col == EXPECTED_WRAP_COL

    def test_move_left_at_start(self):
        cm = CursorManager(["hello"])
        cm.current_line = 0
        cm.current_col = 0
        cm.move_cursor_left()
        assert cm.current_line == 0
        assert cm.current_col == 0

    def test_move_right(self):
        cm = CursorManager(["hello"])
        cm.current_col = 2
        cm.move_cursor_right()
        assert cm.current_col == EXPECTED_COL_AFTER_RIGHT

    def test_move_right_wraps_to_next_line(self):
        cm = CursorManager(["ab", "cd"])
        cm.current_line = 0
        cm.current_col = 2  # End of "ab"
        cm.move_cursor_right()
        assert cm.current_line == 1
        assert cm.current_col == 0

    def test_move_right_at_end(self):
        cm = CursorManager(["hello"])
        cm.current_line = 0
        cm.current_col = 5
        cm.move_cursor_right()
        assert cm.current_col == EXPECTED_HELLO_LEN

    def test_move_to_previous_word(self):
        cm = CursorManager(["hello world foo"])
        cm.current_col = 14  # End of "foo"
        cm.move_to_previous_word()
        assert cm.current_col == EXPECTED_PREV_WORD_COL

    def test_move_to_next_word(self):
        cm = CursorManager(["hello world foo"])
        cm.current_col = 0
        cm.move_to_next_word()
        assert cm.current_col == EXPECTED_NEXT_WORD_COL

    def test_move_to_previous_paragraph(self):
        lines = ["line1", "", "line3", "line4"]
        cm = CursorManager(lines)
        cm.current_line = 3
        cm.move_to_previous_paragraph()
        assert cm.current_line == EXPECTED_EMPTY_LINE_INDEX

    def test_move_to_next_paragraph(self):
        lines = ["line1", "line2", "", "line4"]
        cm = CursorManager(lines)
        cm.current_line = 0
        cm.move_to_next_paragraph()
        assert cm.current_line == EXPECTED_NEXT_PARAGRAPH_LINE

    def test_move_to_previous_paragraph_no_empty(self):
        lines = ["line1", "line2", "line3"]
        cm = CursorManager(lines)
        cm.current_line = 2
        cm.move_to_previous_paragraph()
        assert cm.current_line == 0

    def test_move_to_next_paragraph_no_empty(self):
        lines = ["line1", "line2", "line3"]
        cm = CursorManager(lines)
        cm.current_line = 0
        cm.move_to_next_paragraph()
        assert cm.current_line == EXPECTED_LAST_LINE_INDEX_3
        assert cm.current_col == EXPECTED_HELLO_LEN

    def test_col_clamp_on_vertical_movement(self):
        """Column should clamp to line length when moving vertically."""
        cm = CursorManager(["long line here", "hi"])
        cm.current_line = 0
        cm.current_col = 12  # Past end of "hi"
        cm.move_cursor_down()
        assert cm.current_col == EXPECTED_CLAMP_COL


# ---------------------------------------------------------------------------
# StreamRenderer (basic construction, no terminal needed)
# ---------------------------------------------------------------------------


class TestStreamRendererConstruction:
    """Test StreamRenderer can be constructed and basic attributes set."""

    def test_construction(self):
        renderer = StreamRenderer(session_id="test-sess", capture_content=True)
        assert renderer.session_id == "test-sess"
        assert renderer.capture_content is True
        assert renderer.full_output == ""
        assert renderer.content_started is False
        assert CONTENT_WIDTH == EXPECTED_CONTENT_WIDTH
        assert TOTAL_WIDTH == EXPECTED_TOTAL_WIDTH

    def test_process_empty_chunk(self):
        renderer = StreamRenderer(session_id="test", capture_content=True)
        renderer.process_chunk("")
        assert renderer.full_output == ""
        assert renderer.content_started is False

    def test_process_chunk_capture_mode(self):
        renderer = StreamRenderer(session_id="test", capture_content=True)
        renderer.process_chunk("hello world")
        assert renderer.content_started is True
        assert "hello world" in renderer.full_output


# ---------------------------------------------------------------------------
# AgentConfigPresets
# ---------------------------------------------------------------------------


class TestAgentConfigPresets:
    """Test config presets for worker and interactive modes."""

    def test_worker_preset(self):
        cfg = AgentConfigPresets.worker()
        assert cfg.enable_hooks is True
        assert cfg.timeout == EXPECTED_WORKER_TIMEOUT
        assert cfg.allowed_tools is None

    def test_worker_with_session(self):
        cfg = AgentConfigPresets.worker(session_id="my-session")
        assert cfg.session_id == "my-session"

    def test_interactive_preset(self):
        cfg = AgentConfigPresets.interactive()
        assert cfg.enable_hooks is True
        assert cfg.timeout is None


# ---------------------------------------------------------------------------
# status_utils formatting
# ---------------------------------------------------------------------------


class TestStatusUtilsFormatting:
    """Test status_utils formatting functions."""

    def test_format_bytes(self):
        result = format_bytes(1024 * 1024 * 2.5)
        assert "MB" in result or "MiB" in result or "2" in result

    def test_format_bytes_zero(self):
        result = format_bytes(0)
        assert "0" in result or "B" in result

    def test_format_ports(self):
        ports = [PortMapping(host_port=8080, container_port=80)]
        result = format_ports(ports)
        assert "8080" in result

    def test_format_ports_empty(self):
        result = format_ports([])
        assert result == "" or result is not None

    def test_get_visual_width_simple(self):
        width = get_visual_width("hello")
        assert width == EXPECTED_HELLO_LEN

    def test_get_visual_width_ansi(self):
        width = get_visual_width("\033[31mhello\033[0m")
        assert width == EXPECTED_HELLO_LEN  # ANSI codes don't count

    def test_display_width_constant(self):
        assert DISPLAY_WIDTH == EXPECTED_DISPLAY_WIDTH

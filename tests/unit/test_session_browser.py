"""Unit tests for session_browser and session_detail modules."""

from unittest.mock import MagicMock, patch

from ami.cli.transcript_store import SessionMetadata
from ami.cli_components.session_browser import (
    _build_session_menu_items,
    _format_session_description,
    _format_session_label,
    browse_sessions,
    browse_sessions_with_filter,
)
from ami.cli_components.session_detail import (
    ACTION_BACK,
    ACTION_DELETE,
    ACTION_RESUME,
    _build_action_items,
    run_session_detail,
)

_SESSION_DEFAULTS = {
    "session_id": "019c038b-4470-7e47-b690-5cc910008235",
    "status": "active",
    "entry_count": 15,
    "summary": "Fix login validation flow",
    "provider": "bootloader",
    "model": "default",
    "created": "2026-01-15T10:30:00+00:00",
    "last_active": "2026-01-15T11:45:00+00:00",
    "cwd": "",
}


def _make_session(**overrides: object) -> SessionMetadata:
    """Create a SessionMetadata instance for testing."""
    fields = {**_SESSION_DEFAULTS, **overrides}
    return SessionMetadata(**fields)


# ---------------------------------------------------------------------------
# _format_session_label
# ---------------------------------------------------------------------------


class TestFormatSessionLabel:
    """Tests for _format_session_label."""

    def test_active_session_icon(self) -> None:
        meta = _make_session(status="active")
        label = _format_session_label(meta)
        assert label.startswith("[+]")

    def test_paused_session_icon(self) -> None:
        meta = _make_session(status="paused")
        label = _format_session_label(meta)
        assert label.startswith("[=]")

    def test_completed_session_icon(self) -> None:
        meta = _make_session(status="completed")
        label = _format_session_label(meta)
        assert label.startswith("[x]")

    def test_truncates_session_id(self) -> None:
        meta = _make_session(session_id="019c038b-4470-7e47-b690-5cc910008235")
        label = _format_session_label(meta)
        assert "019c038b-447" in label
        # Full UUID should not appear
        assert "5cc910008235" not in label

    def test_truncates_long_summary(self) -> None:
        long_summary = "A" * 100
        meta = _make_session(summary=long_summary)
        label = _format_session_label(meta)
        assert "..." in label
        assert len(label) < len(long_summary) + 50

    def test_empty_summary_fallback(self) -> None:
        meta = _make_session(summary="")
        label = _format_session_label(meta)
        assert "(no summary)" in label

    def test_includes_entry_count(self) -> None:
        meta = _make_session(entry_count=42)
        label = _format_session_label(meta)
        assert "42 entries" in label

    def test_singular_entry(self) -> None:
        meta = _make_session(entry_count=1)
        label = _format_session_label(meta)
        assert "1 entry" in label


# ---------------------------------------------------------------------------
# _format_session_description
# ---------------------------------------------------------------------------


class TestFormatSessionDescription:
    """Tests for _format_session_description."""

    def test_includes_created_timestamp(self) -> None:
        meta = _make_session(created="2026-01-15T10:30:00+00:00")
        desc = _format_session_description(meta)
        assert "2026-01-15T10:30" in desc

    def test_includes_model(self) -> None:
        meta = _make_session(model="claude-3")
        desc = _format_session_description(meta)
        assert "claude-3" in desc

    def test_includes_dir_when_cwd_set(self) -> None:
        meta = _make_session(cwd="/tmp/test/frontend")
        desc = _format_session_description(meta)
        assert "Dir: frontend" in desc

    def test_no_dir_when_cwd_empty(self) -> None:
        meta = _make_session(cwd="")
        desc = _format_session_description(meta)
        assert "Dir:" not in desc


# ---------------------------------------------------------------------------
# _build_session_menu_items
# ---------------------------------------------------------------------------


class TestBuildSessionMenuItems:
    """Tests for _build_session_menu_items."""

    def test_empty_list_returns_empty(self) -> None:
        assert _build_session_menu_items([]) == []

    def test_grouped_items_have_headers(self) -> None:
        sessions = [
            _make_session(session_id="a1", status="active"),
            _make_session(session_id="p1", status="paused"),
        ]
        items = _build_session_menu_items(sessions, group_by_status=True)
        headers = [i for i in items if i.is_header]
        expected_header_count = 2  # Active header + Paused header
        assert len(headers) == expected_header_count

    def test_header_items_have_is_header_true(self) -> None:
        sessions = [_make_session(session_id="a1", status="active")]
        items = _build_session_menu_items(sessions, group_by_status=True)
        header = items[0]
        assert header.is_header is True
        assert "Active" in header.label

    def test_session_id_used_as_value(self) -> None:
        sessions = [_make_session(session_id="test-uuid-123")]
        items = _build_session_menu_items(sessions, group_by_status=False)
        assert items[0].value == "test-uuid-123"

    def test_ungrouped_mode_no_headers(self) -> None:
        sessions = [
            _make_session(session_id="a1", status="active"),
            _make_session(session_id="p1", status="paused"),
        ]
        items = _build_session_menu_items(sessions, group_by_status=False)
        headers = [i for i in items if i.is_header]
        assert len(headers) == 0
        expected_items = 2
        assert len(items) == expected_items

    def test_skips_empty_status_groups(self) -> None:
        sessions = [_make_session(session_id="p1", status="paused")]
        items = _build_session_menu_items(sessions, group_by_status=True)
        header_labels = [i.label for i in items if i.is_header]
        # Only Paused header, no Active or Completed
        assert len(header_labels) == 1
        assert "Paused" in header_labels[0]

    def test_header_shows_count(self) -> None:
        sessions = [
            _make_session(session_id="a1", status="active"),
            _make_session(session_id="a2", status="active"),
        ]
        items = _build_session_menu_items(sessions, group_by_status=True)
        header = items[0]
        assert "(2)" in header.label


# ---------------------------------------------------------------------------
# browse_sessions
# ---------------------------------------------------------------------------


class TestBrowseSessions:
    """Tests for browse_sessions."""

    @patch("ami.cli_components.session_browser.MenuSelector")
    def test_returns_session_id_on_selection(self, mock_selector_class) -> None:
        mock_item = MagicMock()
        mock_item.value = "selected-session-uuid"

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item]
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.list_sessions.return_value = [
            _make_session(session_id="selected-session-uuid")
        ]

        result = browse_sessions(store)
        assert result == "selected-session-uuid"

    @patch("ami.cli_components.session_browser.MenuSelector")
    def test_returns_none_on_cancel(self, mock_selector_class) -> None:
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.list_sessions.return_value = [_make_session()]

        result = browse_sessions(store)
        assert result is None

    def test_returns_none_on_empty_sessions(self) -> None:
        store = MagicMock()
        store.list_sessions.return_value = []

        result = browse_sessions(store)
        assert result is None

    @patch("ami.cli_components.session_browser.MenuSelector")
    def test_respects_status_filter(self, mock_selector_class) -> None:
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.list_sessions.return_value = [_make_session()]

        browse_sessions(store, status_filter="paused")
        store.list_sessions.assert_called_once_with(status="paused", cwd=None)

    @patch("ami.cli_components.session_browser.MenuSelector")
    def test_limits_max_sessions(self, mock_selector_class) -> None:
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.list_sessions.return_value = [
            _make_session(session_id=f"s{i}") for i in range(50)
        ]

        browse_sessions(store, max_sessions=10)

        # MenuSelector should have been called with limited items
        call_args = mock_selector_class.call_args
        items_passed = call_args[0][0]
        # 10 sessions + headers (at most 3 headers for 3 status groups)
        max_sessions = 10
        assert len([i for i in items_passed if not i.is_header]) <= max_sessions


# ---------------------------------------------------------------------------
# browse_sessions_with_filter
# ---------------------------------------------------------------------------


class TestBrowseSessionsWithFilter:
    """Tests for browse_sessions_with_filter."""

    @patch("ami.cli_components.session_browser.Path")
    @patch("ami.cli_components.session_browser.browse_sessions")
    @patch("ami.cli_components.session_browser.simple_menu_select")
    def test_all_sessions_filter_scoped_to_cwd(
        self, mock_select, mock_browse, mock_path
    ) -> None:
        mock_path.cwd.return_value = MagicMock(__str__=lambda _: "/tmp/test/project")
        mock_select.return_value = "All Sessions"
        mock_browse.return_value = "session-123"

        store = MagicMock()
        result = browse_sessions_with_filter(store)

        assert result == "session-123"
        mock_browse.assert_called_once_with(
            store, status_filter=None, cwd_filter="/tmp/test/project"
        )

    @patch("ami.cli_components.session_browser.simple_menu_select")
    def test_cancel_at_filter_returns_none(self, mock_select) -> None:
        mock_select.return_value = None

        store = MagicMock()
        result = browse_sessions_with_filter(store)

        assert result is None

    @patch("ami.cli_components.session_browser.Path")
    @patch("ami.cli_components.session_browser.browse_sessions")
    @patch("ami.cli_components.session_browser.simple_menu_select")
    def test_paused_filter_scoped_to_cwd(
        self, mock_select, mock_browse, mock_path
    ) -> None:
        mock_path.cwd.return_value = MagicMock(__str__=lambda _: "/tmp/test/project")
        mock_select.return_value = "Paused"
        mock_browse.return_value = "paused-session"

        store = MagicMock()
        result = browse_sessions_with_filter(store)

        mock_browse.assert_called_once_with(
            store, status_filter="paused", cwd_filter="/tmp/test/project"
        )
        assert result == "paused-session"

    @patch("ami.cli_components.session_browser.browse_sessions")
    @patch("ami.cli_components.session_browser.simple_menu_select")
    def test_all_directories_removes_cwd_filter(self, mock_select, mock_browse) -> None:
        mock_select.return_value = "All Directories"
        mock_browse.return_value = "any-session"

        store = MagicMock()
        result = browse_sessions_with_filter(store)

        assert result == "any-session"
        mock_browse.assert_called_once_with(store, status_filter=None, cwd_filter=None)


# ---------------------------------------------------------------------------
# _build_action_items (session_detail)
# ---------------------------------------------------------------------------


class TestBuildActionItems:
    """Tests for _build_action_items."""

    def test_returns_resume_and_delete(self) -> None:
        items = _build_action_items()
        values = [i.value for i in items]
        assert ACTION_RESUME in values
        assert ACTION_DELETE in values
        expected_actions = 2
        assert len(items) == expected_actions

    def test_resume_is_first(self) -> None:
        items = _build_action_items()
        assert items[0].value == ACTION_RESUME
        assert items[1].value == ACTION_DELETE


# ---------------------------------------------------------------------------
# run_session_detail (session_detail)
# ---------------------------------------------------------------------------


class TestRunSessionDetail:
    """Tests for run_session_detail."""

    @patch("ami.cli_components.session_detail.MenuSelector")
    def test_returns_resume(self, mock_selector_class) -> None:
        mock_item = MagicMock()
        mock_item.value = ACTION_RESUME

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item]
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.get_session.return_value = _make_session()

        result = run_session_detail(store, "test-session-id")
        assert result == ACTION_RESUME

    @patch("ami.cli_components.session_detail.MenuSelector")
    def test_returns_delete(self, mock_selector_class) -> None:
        mock_item = MagicMock()
        mock_item.value = ACTION_DELETE

        mock_selector = MagicMock()
        mock_selector.run.return_value = [mock_item]
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.get_session.return_value = _make_session()

        result = run_session_detail(store, "test-session-id")
        assert result == ACTION_DELETE

    @patch("ami.cli_components.session_detail.MenuSelector")
    def test_returns_back_on_cancel(self, mock_selector_class) -> None:
        mock_selector = MagicMock()
        mock_selector.run.return_value = None
        mock_selector_class.return_value = mock_selector

        store = MagicMock()
        store.get_session.return_value = _make_session()

        result = run_session_detail(store, "test-session-id")
        assert result == ACTION_BACK

    def test_returns_back_on_missing_session(self) -> None:
        store = MagicMock()
        store.get_session.return_value = None

        result = run_session_detail(store, "nonexistent")
        assert result == ACTION_BACK

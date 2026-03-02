"""Interactive session browser TUI.

Browse, filter, and select transcript sessions using the MenuSelector component.
Follows the selector.py pattern: domain objects -> MenuItem -> MenuSelector -> result.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ami.cli.transcript_store import SessionMetadata, TranscriptStore
from ami.cli_components.menu_selector import MenuItem, MenuSelector, simple_menu_select

# Status display configuration (ASCII to avoid variable-width emoji in SelectionDialog)
_STATUS_ICONS = {
    "active": "[+]",
    "paused": "[=]",
    "completed": "[x]",
}

# Order for grouping sessions by status
_STATUS_ORDER = ("active", "paused", "completed")

# Display formatting constants
_SESSION_ID_DISPLAY_LEN = 12
_SUMMARY_DISPLAY_LEN = 45
_TIMESTAMP_DISPLAY_LEN = 16
_MAX_VISIBLE_SESSIONS = 15
_DEFAULT_MAX_SESSIONS = 100

# Filter menu options
_FILTER_ALL = "All Sessions"
_FILTER_ACTIVE = "Active"
_FILTER_PAUSED = "Paused"
_FILTER_COMPLETED = "Completed"
_FILTER_ALL_DIRS = "All Directories"

_FILTER_MAP = {
    _FILTER_ALL: None,
    _FILTER_ACTIVE: "active",
    _FILTER_PAUSED: "paused",
    _FILTER_COMPLETED: "completed",
    _FILTER_ALL_DIRS: None,
}


def _format_session_label(meta: SessionMetadata) -> str:
    """Format a session as a single-line display label.

    Format: ``[+] 0194a3b2c4d1  15 entries  Fix login validation...``
    """
    icon = _STATUS_ICONS.get(meta.status, "[?]")
    short_id = meta.session_id[:_SESSION_ID_DISPLAY_LEN]

    summary = (meta.summary or "(no summary)").replace("\n", " ")
    if len(summary) > _SUMMARY_DISPLAY_LEN:
        summary = summary[: _SUMMARY_DISPLAY_LEN - 3] + "..."

    entry_word = "entry" if meta.entry_count == 1 else "entries"
    return f"{icon} {short_id}  {meta.entry_count} {entry_word}  {summary}"


def _format_session_description(meta: SessionMetadata) -> str:
    """Format session metadata as a description line.

    Format: ``Created: 2025-01-15T10:30 | Model: claude-3 | Dir: frontend``
    """
    created = meta.created[:_TIMESTAMP_DISPLAY_LEN]
    parts = [f"Created: {created}", f"Model: {meta.model}"]
    if meta.cwd:
        dir_name = Path(meta.cwd).name or meta.cwd
        parts.append(f"Dir: {dir_name}")
    return " | ".join(parts)


def _build_session_menu_items(
    sessions: list[SessionMetadata],
    group_by_status: bool = True,
) -> list[MenuItem[str]]:
    """Convert SessionMetadata list to MenuItem list.

    When ``group_by_status=True``, inserts header MenuItems between status groups.
    Each session MenuItem has ``value = session_id`` (full UUID).
    """
    if not sessions:
        return []

    if not group_by_status:
        return [
            MenuItem(
                meta.session_id,
                _format_session_label(meta),
                meta.session_id,
                description=_format_session_description(meta),
            )
            for meta in sessions
        ]

    # Group sessions by status
    by_status = {status: list[SessionMetadata]() for status in _STATUS_ORDER}
    for meta in sessions:
        bucket = by_status.get(meta.status)
        if bucket is not None:
            bucket.append(meta)

    items: list[MenuItem[str]] = []
    for status in _STATUS_ORDER:
        group = by_status[status]
        if not group:
            continue

        # Add group header
        header_label = f"{status.capitalize()} ({len(group)})"
        items.append(
            MenuItem(
                f"_header_{status}",
                header_label,
                "",
                is_header=True,
            )
        )

        # Add session items
        items.extend(
            MenuItem(
                meta.session_id,
                _format_session_label(meta),
                meta.session_id,
                description=_format_session_description(meta),
            )
            for meta in group
        )

    return items


def browse_sessions(
    store: TranscriptStore,
    status_filter: str | None = None,
    cwd_filter: str | None = None,
    max_sessions: int = _DEFAULT_MAX_SESSIONS,
) -> str | None:
    """Launch interactive session browser.

    Returns selected session_id or None if cancelled.
    """
    sessions = store.list_sessions(status=status_filter, cwd=cwd_filter)

    if not sessions:
        sys.stdout.write("No sessions found.\n")
        return None

    # Limit to prevent UI lag with 1000+ sessions
    truncated = len(sessions) > max_sessions
    sessions = sessions[:max_sessions]

    # When filtering by a single status, don't group (all same status)
    group_by_status = status_filter is None
    items = _build_session_menu_items(sessions, group_by_status=group_by_status)

    title = "Session Browser"
    if status_filter:
        title = f"Sessions ({status_filter})"
    if truncated:
        title += f" (showing {max_sessions})"

    selector: MenuSelector[str] = MenuSelector(
        items, title, max_visible_items=_MAX_VISIBLE_SESSIONS
    )
    selected = selector.run()

    if selected and selected[0].value:
        return str(selected[0].value)
    return None


def browse_sessions_with_filter(store: TranscriptStore) -> str | None:
    """Two-stage browser: first pick filter, then browse sessions.

    Stage 1: Select status filter (All / Active / Paused / Completed / All Directories).
    Stage 2: Browse sessions matching the filter.

    By default, all filters are scoped to the current working directory.
    "All Directories" removes the cwd constraint and shows all sessions.

    ESC/Backspace at stage 2 returns to stage 1.
    ESC/Backspace at stage 1 exits (returns None).
    """
    current_cwd = str(Path.cwd())
    filter_options = [
        _FILTER_ALL,
        _FILTER_ACTIVE,
        _FILTER_PAUSED,
        _FILTER_COMPLETED,
        _FILTER_ALL_DIRS,
    ]
    while True:
        chosen = simple_menu_select(filter_options, title="Filter Sessions")

        if chosen is None:
            return None

        status_filter = _FILTER_MAP.get(chosen)
        # "All Directories" removes cwd scoping; everything else is cwd-scoped
        cwd_filter = None if chosen == _FILTER_ALL_DIRS else current_cwd
        session_id = browse_sessions(
            store, status_filter=status_filter, cwd_filter=cwd_filter
        )

        if session_id is not None:
            return session_id
        # ESC/Backspace at session list → loop back to filter menu

"""Session detail view with action selection.

After session selection in the browser, presents Resume / Delete actions.
"""

from __future__ import annotations

import sys

from ami.cli.transcript_store import TranscriptStore
from ami.cli_components.menu_selector import MenuItem, MenuSelector

# Action constants returned to caller for dispatch
ACTION_RESUME = "resume"
ACTION_DELETE = "delete"
ACTION_BACK = "back"

_SESSION_ID_DISPLAY_LEN = 12
_SUMMARY_DISPLAY_LEN = 40


def _build_action_items() -> list[MenuItem[str]]:
    """Build the action menu items for a session."""
    return [
        MenuItem(ACTION_RESUME, "Resume session", ACTION_RESUME),
        MenuItem(ACTION_DELETE, "Delete session", ACTION_DELETE),
    ]


def run_session_detail(store: TranscriptStore, session_id: str) -> str:
    """Present Resume / Delete menu for a selected session.

    Returns ``ACTION_RESUME``, ``ACTION_DELETE``, or ``ACTION_BACK`` (ESC).
    """
    meta = store.get_session(session_id)
    if meta is None:
        sys.stderr.write(f"Session not found: {session_id}\n")
        return ACTION_BACK

    summary = (meta.summary or "(no summary)").replace("\n", " ")
    if len(summary) > _SUMMARY_DISPLAY_LEN:
        summary = summary[: _SUMMARY_DISPLAY_LEN - 3] + "..."
    short_id = meta.session_id[:_SESSION_ID_DISPLAY_LEN]
    title = f"{short_id} - {summary}"

    items = _build_action_items()
    selector: MenuSelector[str] = MenuSelector(items, title)
    selected = selector.run()

    if selected and selected[0].value:
        return str(selected[0].value)
    return ACTION_BACK

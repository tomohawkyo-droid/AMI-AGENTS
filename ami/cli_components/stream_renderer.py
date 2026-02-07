"""Stream rendering logic for CLI agent output."""

import sys
import textwrap
import time
from typing import TypedDict

from ami.cli.timer_utils import TimerDisplay
from ami.core.logic import CompletionMarker, parse_completion_marker


class StreamResult(TypedDict):
    """Result from stream rendering completion."""

    session_id: str
    duration: float
    output_length: int
    completion: CompletionMarker


# Constants
CONTENT_WIDTH = 76
TOTAL_WIDTH = 80


class StreamRenderer:
    """Handles TUI rendering for the agent output stream."""

    def __init__(self, session_id: str, capture_content: bool = False):
        self.session_id = session_id
        self.capture_content = capture_content

        self.full_output = ""
        self.started_at = time.time()
        self.timer = TimerDisplay()

        self.content_started = False
        self.box_displayed = False
        self.last_print_ended_with_newline = False
        self.response_box_started = False
        self.response_box_ended = False
        self.line_buffer = ""
        self.in_run_block = False

    def start(self) -> None:
        """Start the renderer (timer)."""
        if not self.capture_content:
            self.timer.start()

    def process_chunk(self, chunk_text: str) -> None:
        """Process and render a chunk of text."""
        if not chunk_text:
            return

        if not self.content_started:
            if not self.capture_content:
                self.timer.stop()
            self.content_started = True
            self.box_displayed = True
            if not self.capture_content:
                sys.stdout.write("┌" + "─" * 78 + "┐\n")
                sys.stdout.flush()
            self.response_box_started = True

        if not self.capture_content:
            self.line_buffer += chunk_text

            if "\n" in self.line_buffer:
                lines = self.line_buffer.split("\n")
                complete_lines = lines[:-1]
                self.line_buffer = lines[-1]

                for line in complete_lines:
                    self._render_line(line)

        self.last_print_ended_with_newline = chunk_text.endswith("\n")
        self.full_output += chunk_text

    def _render_line(self, line: str) -> None:
        """Render a single completed line."""
        display_line = line

        # Display-only replacements
        if "```run" in display_line or "```bash" in display_line:
            display_line = display_line.replace("```run", "</>").replace(
                "```bash", "</>"
            )
            self.in_run_block = True

        # Check for closing fence
        if self.in_run_block and "```" in display_line:
            if display_line.strip() == "```":
                self.in_run_block = False
                return  # Skip printing closing fence line

            display_line = display_line.replace("```", "")
            self.in_run_block = False

        # Print with indentation and word wrapping
        if len(display_line) <= CONTENT_WIDTH:
            print(f"  {display_line}")
        else:
            for wrap_line in textwrap.fill(display_line, width=CONTENT_WIDTH).split(
                "\n"
            ):
                print(f"  {wrap_line}")

    def render_raw_line(self, line: str) -> None:
        """Render a raw line directly without parsing."""
        if not self.content_started:
            if not self.capture_content:
                self.timer.stop()
            self.content_started = True
            self.box_displayed = True

        if len(line) <= CONTENT_WIDTH:
            if not self.capture_content:
                sys.stdout.write("  " + line + "\n")
                sys.stdout.flush()
            self.last_print_ended_with_newline = True
        else:
            wrapped = textwrap.fill(line, width=CONTENT_WIDTH).split("\n")
            for _idx, wrap_line in enumerate(wrapped):
                if not self.capture_content:
                    sys.stdout.write("  " + wrap_line + "\n")
                    sys.stdout.flush()
            self.last_print_ended_with_newline = True
        self.full_output += line + "\n"

    def finish(self) -> StreamResult:
        """Finish rendering and return metadata."""
        # Cleanup display
        if self.timer.is_running:
            self.timer.stop()

        # Flush remaining buffer through normal line rendering
        if not self.capture_content and self.line_buffer:
            self._render_line(self.line_buffer)
            self.line_buffer = ""

        # Close box
        if (
            not self.capture_content
            and self.response_box_started
            and not self.response_box_ended
        ):
            sys.stdout.write("└" + "─" * 78 + "┘\n")
            sys.stdout.flush()
            self.response_box_ended = True

        # Footer
        if not self.capture_content:
            sys.stdout.write(f"\n🤖 {time.strftime('%H:%M:%S')}\n\n")
            sys.stdout.flush()

        return {
            "session_id": self.session_id,
            "duration": time.time() - self.started_at,
            "output_length": len(self.full_output),
            "completion": parse_completion_marker(self.full_output),
        }

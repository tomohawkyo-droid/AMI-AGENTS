"""
Terminal User Interface (TUI) primitives for drawing dialogs and boxes.
"""

import re
import sys

from pydantic import BaseModel

from ami.cli_components.text_input_utils import Colors

# Regex to strip SGR (Select Graphic Rendition) ANSI escape codes.
# Matches color/style codes like \033[31m, \033[1;4m, \033[0m.
# Does NOT strip cursor-movement codes (\033[5A) — those should not
# appear in box/dialog content text.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Strip ANSI SGR escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


def visible_len(text: str) -> int:
    """Get visible length of text (excluding ANSI SGR codes)."""
    return len(strip_ansi(text))


def _format_box_row(
    line: str, width: int, border_color: str, text_color: str, center: bool
) -> str:
    """Format a single content row for a box.

    Guarantees the visible output is exactly ``width`` characters so it
    never wraps in the terminal (which would break line-count tracking).
    """
    inner_width = width - 2  # space between │ and │
    line = line.replace("\n", " ").replace("\r", "")  # newlines break row count
    vis_len = visible_len(line)

    if center:
        # Truncate if needed
        if vis_len > inner_width:
            line = _truncate_to_visible(line, inner_width)
            vis_len = inner_width
        fill = inner_width - vis_len
        l_pad = fill // 2
        r_pad = fill - l_pad
        return (
            f"{border_color}│{Colors.RESET}"
            f"{' ' * l_pad}{text_color}{line}{Colors.RESET}"
            f"{' ' * r_pad}{border_color}│{Colors.RESET}"
        )

    # Left-aligned: │  content  padding  │
    left_pad = 2
    content_max = inner_width - left_pad  # max visible chars for content
    if vis_len > content_max:
        line = _truncate_to_visible(line, content_max)
        vis_len = content_max
    right_pad = inner_width - left_pad - vis_len
    return (
        f"{border_color}│{Colors.RESET}{' ' * left_pad}"
        f"{text_color}{line}{Colors.RESET}"
        f"{' ' * right_pad}{border_color}│{Colors.RESET}"
    )


def _truncate_to_visible(text: str, max_visible: int) -> str:
    """Truncate text so its visible length (excluding ANSI) is at most max_visible.

    Walks character-by-character, preserving ANSI escape sequences but
    counting only visible characters toward the limit.
    """
    if max_visible <= 0:
        return ""
    result: list[str] = []
    visible_count = 0
    i = 0
    while i < len(text):
        # Check for ANSI escape sequence
        if text[i] == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            # Find end of sequence (letter)
            j = i + 2
            while j < len(text) and not text[j].isalpha():
                j += 1
            if j < len(text):
                j += 1  # include the letter
            result.append(text[i:j])
            i = j
        else:
            if visible_count >= max_visible:
                break
            result.append(text[i])
            visible_count += 1
            i += 1
    return "".join(result)


class BoxStyle(BaseModel):
    """Style configuration for drawing boxes."""

    width: int = 60
    border_color: str = Colors.CYAN
    text_color: str = Colors.RESET
    center_content: bool = False


class TUI:
    """Shared TUI drawing utilities."""

    @staticmethod
    def clear_lines(count: int) -> None:
        """Clear the last N lines from the terminal."""
        if count > 0:
            for _ in range(count):
                sys.stdout.write("\033[1A")  # Move cursor up one line
                sys.stdout.write("\033[2K")  # Clear the entire line
            sys.stdout.flush()

    @staticmethod
    def draw_box(
        content: list[str],
        title: str | None = None,
        footer: str | None = None,
        style: BoxStyle | None = None,
    ) -> int:
        """
        Draw a bordered box with content.

        Args:
            content: List of strings to display inside the box
            title: Optional title for the top border
            footer: Optional footer text (e.g. instructions) below the box
            style: Box style configuration (width, colors, centering)

        Returns:
            int: Number of lines printed (for clearing later)
        """
        if style is None:
            style = BoxStyle()
        width = style.width
        border_color = style.border_color
        text_color = style.text_color
        center_content = style.center_content
        lines_printed = 0

        # 1. Top Border
        if title:
            safe_title = f" {title} "
            # Truncate title if too long
            if len(safe_title) > width - 4:
                safe_title = safe_title[: width - 4]

            border_len = (width - len(safe_title)) // 2
            # Adjust for odd widths to ensure alignment
            right_border_len = width - len(safe_title) - border_len

            left_border = f"{border_color}┌{'─' * border_len}{Colors.RESET}"
            title_part = f"{Colors.BOLD}{safe_title}{Colors.RESET}"
            rb_dash = "─" * (right_border_len - 2)
            right_border = f"{border_color}{rb_dash}┐{Colors.RESET}"
            top_line = f"{left_border}{title_part}{right_border}"
        else:
            top_line = f"{border_color}┌{'─' * (width - 2)}┐{Colors.RESET}"

        sys.stdout.write(top_line + "\n")
        lines_printed += 1

        # 2. Content
        # Add a blank line at top padding
        pad = " " * (width - 2)
        blank_row = f"{border_color}│{Colors.RESET}{pad}{border_color}│{Colors.RESET}\n"
        sys.stdout.write(blank_row)
        lines_printed += 1

        for line in content:
            row = _format_box_row(line, width, border_color, text_color, center_content)
            sys.stdout.write(row + "\n")
            lines_printed += 1

        # Add a blank line at bottom padding
        sys.stdout.write(blank_row)
        lines_printed += 1

        # 3. Bottom Border
        bottom_line = f"{border_color}└{'─' * (width - 2)}┘{Colors.RESET}"
        sys.stdout.write(bottom_line + "\n")
        lines_printed += 1

        # 4. Footer
        if footer:
            sys.stdout.write(f"{footer}\n")
            lines_printed += 1

        sys.stdout.flush()
        return lines_printed

    @staticmethod
    def wrap_text(text: str, width: int) -> list[str]:
        """Word wrap that uses visible_len so ANSI codes don't break wrapping."""
        words = text.split()
        lines: list[str] = []
        current_line: list[str] = []
        current_len = 0

        for word in words:
            word_len = visible_len(word)
            separator_len = 1 if current_line else 0
            if current_len + word_len + separator_len <= width:
                current_line.append(word)
                current_len += word_len + separator_len
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_len = word_len

        if current_line:
            lines.append(" ".join(current_line))

        return lines

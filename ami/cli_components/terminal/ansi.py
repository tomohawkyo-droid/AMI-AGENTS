"""ANSI Escape Code Abstraction for Terminal UI.

Provides a clean interface for terminal colors, cursor management, and screen operations,
encapsulating raw escape sequences.
"""

import sys


class AnsiTerminal:
    """Encapsulates ANSI escape sequences for terminal manipulation."""

    # Formatting
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    STRIKETHROUGH = "\033[9m"

    # Foreground Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background Colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    @staticmethod
    def move_up(n: int = 1) -> None:
        """Move cursor up n lines."""
        if n > 0:
            sys.stdout.write(f"\033[{n}A")
            sys.stdout.flush()

    @staticmethod
    def move_down(n: int = 1) -> None:
        """Move cursor down n lines."""
        if n > 0:
            sys.stdout.write(f"\033[{n}B")
            sys.stdout.flush()

    @staticmethod
    def move_right(n: int = 1) -> None:
        """Move cursor right n columns."""
        if n > 0:
            sys.stdout.write(f"\033[{n}C")
            sys.stdout.flush()

    @staticmethod
    def move_left(n: int = 1) -> None:
        """Move cursor left n columns."""
        if n > 0:
            sys.stdout.write(f"\033[{n}D")
            sys.stdout.flush()

    @staticmethod
    def move_to_column(n: int = 1) -> None:
        """Move cursor to specified column."""
        sys.stdout.write(f"\033[{n}G")
        sys.stdout.flush()

    @staticmethod
    def clear_line() -> None:
        """Clear the entire current line."""
        sys.stdout.write("\033[2K")
        sys.stdout.flush()

    @staticmethod
    def clear_screen() -> None:
        """Clear the entire screen."""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    @staticmethod
    def hide_cursor() -> None:
        """Hide the terminal cursor."""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor() -> None:
        """Show the terminal cursor."""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @staticmethod
    def colorize(text: str, color_code: str) -> str:
        """Wrap text with a color code and reset."""
        return f"{color_code}{text}{AnsiTerminal.RESET}"

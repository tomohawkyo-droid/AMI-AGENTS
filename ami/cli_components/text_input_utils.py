"""
Terminal UI utilities for the text input component.
"""

import datetime
import sys
import termios
import tty

from ami.cli_components.terminal.ansi import AnsiTerminal

# ASCII control character codes
ESC = 27  # Escape character (arrow keys prefix)

# Bracketed paste mode sequences
BRACKETED_PASTE_START = "\033[200~"
BRACKETED_PASTE_END = "\033[201~"
BRACKETED_PASTE_ENABLE = "\033[?2004h"
BRACKETED_PASTE_DISABLE = "\033[?2004l"
BRACKET = 91  # '[' character (ANSI sequence prefix)
OSC_PREFIX = 79  # 'O' character (OSC sequence prefix, used for F1-F4)
UP_ARROW = 65  # Up arrow key sequence
DOWN_ARROW = 66  # Down arrow key sequence
RIGHT_ARROW = 67  # Right arrow key sequence
LEFT_ARROW = 68  # Left arrow key sequence
ONE = 49  # '1' character (for Ctrl+arrow sequences)
SEMICOLON = 59  # ';' character (for Ctrl+arrow sequences)
FIVE = 53  # '5' character (Ctrl modifier for arrow keys)
TILDE = 126  # '~' character
CTRL_H_CODE = 8  # Ctrl+H (often sent by Ctrl+Backspace in some terminals)
CTRL_C = 3  # Ctrl+C (interrupt)
CTRL_S = 19  # Ctrl+S (send to agent)
BACKSPACE = 127  # Backspace key
ENTER_CR = 13  # Enter (carriage return)
ENTER_LF = 10  # Enter (line feed)
TAB = 9  # Tab
CTRL_U = 21  # Ctrl+U (delete entire line)
CTRL_A = 1  # Ctrl+A (go to beginning of line)
CTRL_W = 23  # Ctrl+W (delete word)
PRINTABLE_MIN = 32  # First printable ASCII character
PRINTABLE_MAX = 126  # Last printable ASCII character
CONTROL_MAX = 31  # Last control character (0-31)


# ANSI color codes
class Colors:
    RESET = AnsiTerminal.RESET
    BOLD = AnsiTerminal.BOLD
    REVERSE = (
        AnsiTerminal.REVERSE
    )  # Inverted video (black on white background rectangle)
    BLACK = AnsiTerminal.BLACK
    RED = AnsiTerminal.RED
    GREEN = AnsiTerminal.GREEN
    YELLOW = AnsiTerminal.YELLOW
    BLUE = AnsiTerminal.BLUE
    MAGENTA = AnsiTerminal.MAGENTA
    CYAN = AnsiTerminal.CYAN
    WHITE = AnsiTerminal.WHITE
    BG_RED = AnsiTerminal.BG_RED
    BG_GREEN = AnsiTerminal.BG_GREEN
    BG_YELLOW = AnsiTerminal.BG_YELLOW
    BG_BLUE = AnsiTerminal.BG_BLUE
    BG_MAGENTA = AnsiTerminal.BG_MAGENTA
    BG_CYAN = AnsiTerminal.BG_CYAN
    BG_WHITE = AnsiTerminal.BG_WHITE


def getchar() -> str:
    """Get a single character from standard input without pressing enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    # Modify terminal settings:
    # 1. Disable XON/XOFF flow control (Ctrl+S and Ctrl+Q)
    # 2. Disable ICRNL (Input CR to NL translation) to distinguish CR (13) from LF (10)
    new_settings = termios.tcgetattr(fd)
    new_settings[6][termios.VSTOP] = b"\x00"  # Disable XOFF (Ctrl+S)
    new_settings[6][termios.VSTART] = b"\x00"  # Disable XON (Ctrl+Q)
    new_settings[0] = new_settings[0] & ~termios.ICRNL  # Disable ICRNL
    termios.tcsetattr(fd, termios.TCSANOW, new_settings)

    try:
        tty.setcbreak(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        # Restore original settings
        termios.tcsetattr(fd, termios.TCSANOW, old_settings)
    return ch


def get_char_with_ordinals() -> tuple[str, int]:
    """Read a character and return it along with its ordinal value."""
    ch = getchar()
    return ch, ord(ch)


def _handle_escape_sequence() -> str | None:
    """Handle escape sequences (arrow keys, etc)."""
    _ch2, ord2 = get_char_with_ordinals()
    if ord2 == BRACKET:  # '[' character (ANSI sequence prefix)
        return _handle_ansi_sequence()
    if ord2 == OSC_PREFIX:  # 'O' character (F1-F4 keys prefix)
        return _handle_osc_sequence()
    if ord2 in {ENTER_CR, ENTER_LF}:  # Alt+Enter
        return "ALT_ENTER"

    # If not a recognized sequence, return the original ESC
    return (
        "ESC_NOT_HANDLED"  # Special marker to indicate original ESC should be returned
    )


def _handle_osc_sequence() -> str:
    """Handle OSC escape sequences for F1-F4 keys."""
    _ch3, ord3 = get_char_with_ordinals()
    if ord3 == ord("P"):  # F1
        return "F1"
    if ord3 == ord("Q"):  # F2
        return "F2"
    if ord3 == ord("R"):  # F3
        return "F3"
    if ord3 == ord("S"):  # F4
        return "F4"
    return "ESC_NOT_HANDLED"


def _handle_ansi_sequence() -> str:
    """Handle ANSI escape sequences for arrow keys and special combinations."""
    _ch3, ord3 = get_char_with_ordinals()

    # Check for bracketed paste sequences first
    paste_result = _check_paste_sequences(ord3)
    if paste_result != "ESC_NOT_HANDLED":
        return paste_result

    # Handle arrow keys and special sequences
    return _handle_arrow_keys(ord3)


def _check_paste_sequences(ord3: int) -> str:
    """Check for bracketed paste sequences and return appropriate result."""
    # Check for bracketed paste sequences: ESC[200~ (start) and ESC[201~ (end)
    if ord3 == ord("2"):  # Check for '2' - could be bracketed paste
        return _check_bracketed_paste_sequence()
    # Alternative bracketed paste sequences: ESC0~ (start) and ESC01~ (end) - some terminals
    if ord3 == ord("0"):
        return _check_alternative_paste_sequence()
    return "ESC_NOT_HANDLED"


def _check_bracketed_paste_sequence() -> str:
    """Check for bracketed paste sequence ESC[200~ (start) and ESC[201~ (end)."""
    _ch4, ord4 = get_char_with_ordinals()
    if ord4 == ord("0"):
        _ch5, ord5 = get_char_with_ordinals()
        if ord5 == ord("0"):
            _ch6, ord6 = get_char_with_ordinals()
            if ord6 == ord("~"):  # ESC[200~ - paste start
                return "PASTE_START"
        elif ord5 == ord("1"):
            _ch6, ord6 = get_char_with_ordinals()
            if ord6 == ord("~"):  # ESC[201~ - paste end
                return "PASTE_END"
    return "ESC_NOT_HANDLED"


def _check_alternative_paste_sequence() -> str:
    """Check for alternative paste sequences like ESC0~ and ESC01~."""
    _ch4, ord4 = get_char_with_ordinals()
    if ord4 == ord("~"):  # ESC0~ - alternative paste start
        return "PASTE_START_ALT"
    if ord4 == ord("1"):
        _ch5, ord5 = get_char_with_ordinals()
        if ord5 == ord("~"):  # ESC01~ - alternative paste end
            return "PASTE_END_ALT"
    return "ESC_NOT_HANDLED"


def _handle_arrow_keys(ord3: int) -> str:
    """Handle arrow keys and other special sequences."""
    # Simple arrow key mapping
    arrow_map = {
        UP_ARROW: "UP",
        DOWN_ARROW: "DOWN",
        RIGHT_ARROW: "RIGHT",
        LEFT_ARROW: "LEFT",
    }
    if ord3 in arrow_map:
        return arrow_map[ord3]

    # '1' - Check for Ctrl+Arrow combinations or function keys
    if ord3 == ONE:
        _ch4, ord4 = get_char_with_ordinals()
        if ord4 == ord("1"):  # ESC[11~ (F1)
            _ch5, ord5 = get_char_with_ordinals()
            if ord5 == TILDE:
                return "F1"
        elif ord4 == SEMICOLON:  # ESC[1;5X (Ctrl+Arrow)
            return _handle_ctrl_arrow_sequence_after_semicolon()

    return "ESC_NOT_HANDLED"


def _handle_ctrl_arrow_sequence_after_semicolon() -> str:
    """Handle the rest of Ctrl+Arrow sequence after semicolon."""
    _ch5, ord5 = get_char_with_ordinals()  # Should be '5'
    if ord5 != FIVE:  # '5' (Ctrl modifier)
        return "ESC_NOT_HANDLED"

    _ch6, ord6 = get_char_with_ordinals()  # Direction: A, B, C, D
    ctrl_arrow_map = {
        UP_ARROW: "CTRL_UP",
        DOWN_ARROW: "CTRL_DOWN",
        RIGHT_ARROW: "CTRL_RIGHT",
        LEFT_ARROW: "CTRL_LEFT",
    }
    return ctrl_arrow_map.get(ord6, "ESC_NOT_HANDLED")


def _handle_control_characters(ord1: int) -> str | None:
    """Handle various control characters."""
    if ord1 == CTRL_C:
        raise KeyboardInterrupt

    # Map control characters to their action strings
    control_map = {
        CTRL_S: "EOF",
        BACKSPACE: "BACKSPACE",
        ENTER_CR: "ENTER",
        ENTER_LF: "CTRL_ENTER",
        TAB: "\t",
        CTRL_U: "DELETE_LINE",
        CTRL_A: "HOME",
        CTRL_W: "DELETE_WORD",
        CTRL_H_CODE: "BACKSPACE_WORD",
    }
    return control_map.get(ord1)


def read_key_sequence() -> str | int | None:
    """Read potential multi-character key sequences like arrow keys."""
    ch1, ord1 = get_char_with_ordinals()

    # Check if this is an escape sequence (like arrow keys)
    if ord1 == ESC:  # ESC character
        result = _handle_escape_sequence()
        if result == "ESC_NOT_HANDLED":
            return ch1  # Return original ESC character
        return result

    # Handle control characters
    control_result = _handle_control_characters(ord1)
    if control_result is not None:
        return control_result

    # Handle printable characters
    if PRINTABLE_MIN <= ord1 <= PRINTABLE_MAX:  # Printable ASCII characters
        return ch1

    # Filter out other control characters to prevent them from appearing in content
    # Control characters are typically 0-31 and 127, we've already handled the useful ones
    # So we'll return a special code for unhandled control characters to skip them
    if 0 <= ord1 <= CONTROL_MAX and ord1 not in [
        CTRL_C,
        TAB,
        ENTER_LF,
        ENTER_CR,
        CTRL_S,
        CTRL_U,
        CTRL_W,
        ESC,
        CTRL_H_CODE,
    ]:  # Skip handled control chars
        return None  # Skip unhandled control characters
    return ch1


def display_final_output(lines: list[str], message: str) -> None:
    """Display final output with borders, indentation, and timestamp message."""
    # Fixed 80-character width for border consistency
    effective_width = 80  # Fixed width of 80 characters

    # Show opening horizontal border
    sys.stdout.write(f"{Colors.CYAN}┌{'─' * (effective_width - 2)}┐{Colors.RESET}\n")
    sys.stdout.flush()

    # Show the text that was entered with 2-character indentation
    if lines:
        for line in lines:
            # Add 2-character indentation to each line
            indented_line = f"  {line}"
            # Truncate line to fit within the 80-char width (80 - 2 for borders = 78)
            content_width = effective_width - 2
            if len(indented_line) > content_width:
                indented_line = indented_line[:content_width]
            indented_line = indented_line.ljust(content_width)  # Pad if shorter
            sys.stdout.write(f"{indented_line}\n")
            sys.stdout.flush()
    else:
        empty_line = "  ".ljust(
            effective_width - 2
        )  # 2-space indent padded to content width
        sys.stdout.write(f"{empty_line}\n")
        sys.stdout.flush()

    # Show closing horizontal border
    sys.stdout.write(f"{Colors.CYAN}└{'─' * (effective_width - 2)}┘{Colors.RESET}")
    sys.stdout.flush()

    # Add newline and print timestamp message using manual sys calls
    sys.stdout.write("\n")
    sys.stdout.flush()
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    # Clean output: just emoji and time, similar to the query mode style
    if "Sent" in message:
        sys.stdout.write(f"💬 {timestamp}\n")
    else:
        sys.stdout.write(f"{message} {timestamp}\n")
    sys.stdout.flush()
    # Add one more newline before returning so the prompt appears on a new line
    sys.stdout.write("\n")
    sys.stdout.flush()

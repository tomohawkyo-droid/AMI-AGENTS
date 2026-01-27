"""Unit tests for text_input_utils - constants, getchar, escape/ANSI/paste sequences."""

from unittest.mock import patch

from ami.cli_components.text_input_utils import (
    BACKSPACE,
    BRACKET,
    BRACKETED_PASTE_DISABLE,
    BRACKETED_PASTE_ENABLE,
    BRACKETED_PASTE_END,
    BRACKETED_PASTE_START,
    CONTROL_MAX,
    CTRL_A,
    CTRL_C,
    CTRL_H_CODE,
    CTRL_S,
    CTRL_U,
    CTRL_W,
    DOWN_ARROW,
    ENTER_CR,
    ENTER_LF,
    ESC,
    FIVE,
    LEFT_ARROW,
    ONE,
    OSC_PREFIX,
    PRINTABLE_MAX,
    PRINTABLE_MIN,
    RIGHT_ARROW,
    SEMICOLON,
    TAB,
    TILDE,
    UP_ARROW,
    Colors,
    _check_bracketed_paste_sequence,
    _check_paste_sequences,
    _handle_ansi_sequence,
    _handle_escape_sequence,
    _handle_osc_sequence,
    get_char_with_ordinals,
    getchar,
)

EXPECTED_ESC_VALUE = 27
EXPECTED_UP_ARROW_VALUE = 65
EXPECTED_DOWN_ARROW_VALUE = 66
EXPECTED_RIGHT_ARROW_VALUE = 67
EXPECTED_LEFT_ARROW_VALUE = 68
EXPECTED_BRACKET_VALUE = 91
EXPECTED_OSC_PREFIX_VALUE = 79
EXPECTED_ONE_VALUE = 49
EXPECTED_SEMICOLON_VALUE = 59
EXPECTED_FIVE_VALUE = 53
EXPECTED_TILDE_VALUE = 126
EXPECTED_CTRL_H_CODE_VALUE = 8
EXPECTED_CTRL_C_VALUE = 3
EXPECTED_CTRL_S_VALUE = 19
EXPECTED_BACKSPACE_VALUE = 127
EXPECTED_ENTER_CR_VALUE = 13
EXPECTED_ENTER_LF_VALUE = 10
EXPECTED_TAB_VALUE = 9
EXPECTED_CTRL_U_VALUE = 21
EXPECTED_CTRL_W_VALUE = 23
EXPECTED_PRINTABLE_MIN_VALUE = 32
EXPECTED_PRINTABLE_MAX_VALUE = 126
EXPECTED_CONTROL_MAX_VALUE = 31
EXPECTED_ORDINAL_A = 65


class TestConstants:
    """Tests for module constants."""

    def test_escape_constant(self):
        """Test ESC constant value."""
        assert ESC == EXPECTED_ESC_VALUE

    def test_bracketed_paste_sequences(self):
        """Test bracketed paste sequence constants."""
        assert BRACKETED_PASTE_START == "\033[200~"
        assert BRACKETED_PASTE_END == "\033[201~"
        assert BRACKETED_PASTE_ENABLE == "\033[?2004h"
        assert BRACKETED_PASTE_DISABLE == "\033[?2004l"

    def test_arrow_key_constants(self):
        """Test arrow key sequence constants."""
        assert UP_ARROW == EXPECTED_UP_ARROW_VALUE
        assert DOWN_ARROW == EXPECTED_DOWN_ARROW_VALUE
        assert RIGHT_ARROW == EXPECTED_RIGHT_ARROW_VALUE
        assert LEFT_ARROW == EXPECTED_LEFT_ARROW_VALUE

    def test_bracket_and_prefix_constants(self):
        """Test bracket and prefix constants."""
        assert BRACKET == EXPECTED_BRACKET_VALUE
        assert OSC_PREFIX == EXPECTED_OSC_PREFIX_VALUE

    def test_control_modifier_constants(self):
        """Test control modifier constants."""
        assert ONE == EXPECTED_ONE_VALUE
        assert SEMICOLON == EXPECTED_SEMICOLON_VALUE
        assert FIVE == EXPECTED_FIVE_VALUE
        assert TILDE == EXPECTED_TILDE_VALUE

    def test_control_character_constants(self):
        """Test control character constants."""
        assert CTRL_H_CODE == EXPECTED_CTRL_H_CODE_VALUE
        assert CTRL_C == EXPECTED_CTRL_C_VALUE
        assert CTRL_S == EXPECTED_CTRL_S_VALUE
        assert BACKSPACE == EXPECTED_BACKSPACE_VALUE
        assert ENTER_CR == EXPECTED_ENTER_CR_VALUE
        assert ENTER_LF == EXPECTED_ENTER_LF_VALUE
        assert TAB == EXPECTED_TAB_VALUE
        assert CTRL_U == EXPECTED_CTRL_U_VALUE
        assert CTRL_A == 1
        assert CTRL_W == EXPECTED_CTRL_W_VALUE

    def test_printable_range_constants(self):
        """Test printable character range constants."""
        assert PRINTABLE_MIN == EXPECTED_PRINTABLE_MIN_VALUE
        assert PRINTABLE_MAX == EXPECTED_PRINTABLE_MAX_VALUE
        assert CONTROL_MAX == EXPECTED_CONTROL_MAX_VALUE


class TestColors:
    """Tests for Colors class."""

    def test_has_reset(self):
        """Test Colors has RESET attribute."""
        assert hasattr(Colors, "RESET")
        assert "\033[" in Colors.RESET

    def test_has_bold(self):
        """Test Colors has BOLD attribute."""
        assert hasattr(Colors, "BOLD")

    def test_has_reverse(self):
        """Test Colors has REVERSE attribute."""
        assert hasattr(Colors, "REVERSE")

    def test_has_color_codes(self):
        """Test Colors has color code attributes."""
        assert hasattr(Colors, "RED")
        assert hasattr(Colors, "GREEN")
        assert hasattr(Colors, "YELLOW")
        assert hasattr(Colors, "BLUE")
        assert hasattr(Colors, "MAGENTA")
        assert hasattr(Colors, "CYAN")
        assert hasattr(Colors, "WHITE")
        assert hasattr(Colors, "BLACK")

    def test_has_background_colors(self):
        """Test Colors has background color attributes."""
        assert hasattr(Colors, "BG_RED")
        assert hasattr(Colors, "BG_GREEN")
        assert hasattr(Colors, "BG_YELLOW")
        assert hasattr(Colors, "BG_BLUE")
        assert hasattr(Colors, "BG_MAGENTA")
        assert hasattr(Colors, "BG_CYAN")
        assert hasattr(Colors, "BG_WHITE")


class TestGetcharMocked:
    """Tests for getchar function with mocked terminal."""

    @patch("ami.cli_components.text_input_utils.termios")
    @patch("ami.cli_components.text_input_utils.tty")
    @patch("ami.cli_components.text_input_utils.sys.stdin")
    def test_getchar_returns_character(self, mock_stdin, mock_tty, mock_termios):
        """Test getchar returns character from stdin."""
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "a"
        mock_termios.tcgetattr.return_value = [[], [], [], [], [], [], {}]

        result = getchar()

        assert result == "a"

    @patch("ami.cli_components.text_input_utils.termios")
    @patch("ami.cli_components.text_input_utils.tty")
    @patch("ami.cli_components.text_input_utils.sys.stdin")
    def test_getchar_restores_settings(self, mock_stdin, mock_tty, mock_termios):
        """Test getchar restores terminal settings."""
        mock_stdin.fileno.return_value = 0
        mock_stdin.read.return_value = "x"
        old_settings = [1, 2, 3, 4, 5, 6, {b"test": b"val"}]
        mock_termios.tcgetattr.return_value = old_settings

        getchar()

        mock_termios.tcsetattr.assert_called()


class TestGetCharWithOrdinals:
    """Tests for get_char_with_ordinals function."""

    @patch("ami.cli_components.text_input_utils.getchar")
    def test_returns_char_and_ordinal(self, mock_getchar):
        """Test returns tuple of char and ordinal."""
        mock_getchar.return_value = "A"

        ch, ord_val = get_char_with_ordinals()

        assert ch == "A"
        assert ord_val == EXPECTED_ORDINAL_A


class TestHandleEscapeSequence:
    """Tests for _handle_escape_sequence function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_handles_bracket_ansi(self, mock_get_char):
        """Test handles ANSI sequence with bracket."""
        # First call: bracket, second call: up arrow
        mock_get_char.side_effect = [("[", BRACKET), ("A", UP_ARROW)]

        result = _handle_escape_sequence()

        assert result == "UP"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_handles_osc_prefix(self, mock_get_char):
        """Test handles OSC sequence prefix."""
        # OSC prefix 'O' followed by 'P' for F1
        mock_get_char.side_effect = [("O", OSC_PREFIX), ("P", ord("P"))]

        result = _handle_escape_sequence()

        assert result == "F1"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_handles_alt_enter(self, mock_get_char):
        """Test handles Alt+Enter."""
        mock_get_char.return_value = ("\r", ENTER_CR)

        result = _handle_escape_sequence()

        assert result == "ALT_ENTER"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_handles_alt_enter_lf(self, mock_get_char):
        """Test handles Alt+Enter with LF."""
        mock_get_char.return_value = ("\n", ENTER_LF)

        result = _handle_escape_sequence()

        assert result == "ALT_ENTER"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_unrecognized_returns_not_handled(self, mock_get_char):
        """Test unrecognized sequence returns ESC_NOT_HANDLED."""
        mock_get_char.return_value = ("x", ord("x"))

        result = _handle_escape_sequence()

        assert result == "ESC_NOT_HANDLED"


class TestHandleOscSequence:
    """Tests for _handle_osc_sequence function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_f1_key(self, mock_get_char):
        """Test F1 key detection."""
        mock_get_char.return_value = ("P", ord("P"))

        result = _handle_osc_sequence()

        assert result == "F1"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_f2_key(self, mock_get_char):
        """Test F2 key detection."""
        mock_get_char.return_value = ("Q", ord("Q"))

        result = _handle_osc_sequence()

        assert result == "F2"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_f3_key(self, mock_get_char):
        """Test F3 key detection."""
        mock_get_char.return_value = ("R", ord("R"))

        result = _handle_osc_sequence()

        assert result == "F3"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_f4_key(self, mock_get_char):
        """Test F4 key detection."""
        mock_get_char.return_value = ("S", ord("S"))

        result = _handle_osc_sequence()

        assert result == "F4"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_unknown_returns_not_handled(self, mock_get_char):
        """Test unknown OSC sequence."""
        mock_get_char.return_value = ("X", ord("X"))

        result = _handle_osc_sequence()

        assert result == "ESC_NOT_HANDLED"


class TestHandleAnsiSequence:
    """Tests for _handle_ansi_sequence function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_handles_arrow_key(self, mock_get_char):
        """Test handles arrow key sequence."""
        mock_get_char.return_value = ("A", UP_ARROW)

        result = _handle_ansi_sequence()

        assert result == "UP"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_checks_paste_sequences(self, mock_get_char):
        """Test checks for paste sequences."""
        # '2' followed by paste sequence chars
        mock_get_char.side_effect = [
            ("2", ord("2")),
            ("0", ord("0")),
            ("0", ord("0")),
            ("~", ord("~")),
        ]

        result = _handle_ansi_sequence()

        assert result == "PASTE_START"


class TestCheckPasteSequences:
    """Tests for _check_paste_sequences function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_paste_start_with_2(self, mock_get_char):
        """Test paste start sequence with '2'."""
        mock_get_char.side_effect = [
            ("0", ord("0")),
            ("0", ord("0")),
            ("~", ord("~")),
        ]

        result = _check_paste_sequences(ord("2"))

        assert result == "PASTE_START"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_alternative_paste_with_0(self, mock_get_char):
        """Test alternative paste sequence with '0'."""
        mock_get_char.return_value = ("~", ord("~"))

        result = _check_paste_sequences(ord("0"))

        assert result == "PASTE_START_ALT"

    def test_not_paste_returns_not_handled(self):
        """Test non-paste character returns ESC_NOT_HANDLED."""
        result = _check_paste_sequences(ord("X"))

        assert result == "ESC_NOT_HANDLED"


class TestCheckBracketedPasteSequence:
    """Tests for _check_bracketed_paste_sequence function."""

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_paste_start(self, mock_get_char):
        """Test ESC[200~ paste start detection."""
        mock_get_char.side_effect = [
            ("0", ord("0")),
            ("0", ord("0")),
            ("~", ord("~")),
        ]

        result = _check_bracketed_paste_sequence()

        assert result == "PASTE_START"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_paste_end(self, mock_get_char):
        """Test ESC[201~ paste end detection."""
        mock_get_char.side_effect = [
            ("0", ord("0")),
            ("1", ord("1")),
            ("~", ord("~")),
        ]

        result = _check_bracketed_paste_sequence()

        assert result == "PASTE_END"

    @patch("ami.cli_components.text_input_utils.get_char_with_ordinals")
    def test_not_paste_returns_not_handled(self, mock_get_char):
        """Test non-paste sequence returns ESC_NOT_HANDLED."""
        mock_get_char.side_effect = [("X", ord("X"))]

        result = _check_bracketed_paste_sequence()

        assert result == "ESC_NOT_HANDLED"

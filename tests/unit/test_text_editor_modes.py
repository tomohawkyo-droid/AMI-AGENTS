"""Tests for TextEditor paste, normal, key processing, run."""

from unittest.mock import MagicMock, patch

from ami.cli_components.text_editor import TextEditor

EXPECTED_COL_AFTER_INSERT = 2


class TestProcessPasteModeKey:
    """Tests for TextEditor._process_paste_mode_key method."""

    def test_accumulates_characters(self) -> None:
        """Test accumulates characters in paste buffer."""
        editor = TextEditor()
        editor.in_paste_mode = True
        display = MagicMock()

        editor._process_paste_mode_key("a", display)
        editor._process_paste_mode_key("b", display)
        editor._process_paste_mode_key("c", display)

        assert editor.paste_buffer == "abc"

    def test_converts_enter_to_newline(self) -> None:
        """Test converts ENTER to newline in paste mode."""
        editor = TextEditor()
        editor.in_paste_mode = True
        display = MagicMock()

        editor._process_paste_mode_key("ENTER", display)

        assert editor.paste_buffer == "\n"

    def test_exits_paste_mode_on_end(self) -> None:
        """Test exits paste mode on PASTE_END."""
        editor = TextEditor()
        editor.in_paste_mode = True
        editor.paste_buffer = "pasted text"
        display = MagicMock()

        editor._process_paste_mode_key("PASTE_END", display)

        assert editor.in_paste_mode is False
        assert editor.paste_buffer == ""
        assert editor.lines == ["pasted text"]

    def test_exits_paste_mode_on_alt_end(self) -> None:
        """Test exits paste mode on PASTE_END_ALT."""
        editor = TextEditor()
        editor.in_paste_mode = True
        editor.paste_buffer = "text"
        display = MagicMock()

        editor._process_paste_mode_key("PASTE_END_ALT", display)

        assert editor.in_paste_mode is False


class TestProcessNormalModeKey:
    """Tests for TextEditor._process_normal_mode_key method."""

    def test_enters_paste_mode_on_paste_start(self) -> None:
        """Test enters paste mode on PASTE_START."""
        editor = TextEditor()
        display = MagicMock()

        result = editor._process_normal_mode_key("PASTE_START", display)

        assert editor.in_paste_mode is True
        assert editor.paste_buffer == ""
        assert result is False

    def test_enters_paste_mode_on_alt_start(self) -> None:
        """Test enters paste mode on PASTE_START_ALT."""
        editor = TextEditor()
        display = MagicMock()

        editor._process_normal_mode_key("PASTE_START_ALT", display)

        assert editor.in_paste_mode is True


class TestHandleNavigationCommandKeys:
    """Tests for TextEditor._handle_navigation_command_keys method."""

    def test_enter_returns_true(self) -> None:
        """Test ENTER key returns True to exit."""
        editor = TextEditor()
        display = MagicMock()

        result = editor._handle_navigation_command_keys("ENTER", display)

        assert result is True

    def test_eof_returns_true(self) -> None:
        """Test EOF (Ctrl+S) returns True to exit."""
        editor = TextEditor()
        display = MagicMock()

        result = editor._handle_navigation_command_keys("EOF", display)

        assert result is True

    def test_alt_enter_adds_newline(self) -> None:
        """Test ALT_ENTER adds newline."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 5
        display = MagicMock()

        result = editor._handle_navigation_command_keys("ALT_ENTER", display)

        assert result is False
        assert editor.lines == ["hello", ""]

    def test_ctrl_enter_adds_newline(self) -> None:
        """Test CTRL_ENTER adds newline."""
        editor = TextEditor("hello")
        editor.cursor_manager.current_col = 5
        display = MagicMock()

        result = editor._handle_navigation_command_keys("CTRL_ENTER", display)

        assert result is False
        assert editor.lines == ["hello", ""]

    def test_f1_toggles_help(self) -> None:
        """Test F1 toggles help display."""
        editor = TextEditor()
        display = MagicMock()
        display.show_help = False

        editor._handle_navigation_command_keys("F1", display)

        assert display.show_help is True

    def test_navigation_keys_move_cursor(self) -> None:
        """Test navigation keys move cursor."""
        editor = TextEditor("hello\nworld")
        display = MagicMock()

        editor._handle_navigation_command_keys("DOWN", display)
        assert editor.cursor_manager.current_line == 1

        editor._handle_navigation_command_keys("UP", display)
        assert editor.cursor_manager.current_line == 0


class TestHandleCharacterInput:
    """Tests for TextEditor._handle_character_input method."""

    def test_inserts_single_character(self) -> None:
        """Test inserts single character at cursor."""
        editor = TextEditor("hllo")
        editor.cursor_manager.current_col = 1
        display = MagicMock()

        editor._handle_character_input("e", display)

        assert editor.lines == ["hello"]
        assert editor.cursor_manager.current_col == EXPECTED_COL_AFTER_INSERT

    def test_inserts_at_end(self) -> None:
        """Test inserts character at end of line."""
        editor = TextEditor("hell")
        editor.cursor_manager.current_col = 4
        display = MagicMock()

        editor._handle_character_input("o", display)

        assert editor.lines == ["hello"]

    def test_ignores_multichar_strings(self) -> None:
        """Test ignores multi-character strings."""
        editor = TextEditor("hello")
        display = MagicMock()

        editor._handle_character_input("UNKNOWN_KEY", display)

        assert editor.lines == ["hello"]


class TestProcessKey:
    """Tests for TextEditor._process_key method."""

    def test_delegates_to_paste_mode(self) -> None:
        """Test delegates to paste mode when in paste mode."""
        editor = TextEditor()
        editor.in_paste_mode = True
        display = MagicMock()

        with patch.object(editor, "_process_paste_mode_key") as mock:
            mock.return_value = False
            editor._process_key("a", display)

            mock.assert_called_once_with("a", display)

    def test_delegates_to_normal_mode(self) -> None:
        """Test delegates to normal mode when not in paste mode."""
        editor = TextEditor()
        display = MagicMock()

        with patch.object(editor, "_process_normal_mode_key") as mock:
            mock.return_value = False
            editor._process_key("a", display)

            mock.assert_called_once_with("a", display)


class TestRun:
    """Tests for TextEditor.run method."""

    @patch("ami.cli_components.text_editor.read_key_sequence")
    @patch("ami.cli_components.text_editor.EditorDisplay")
    def test_returns_text_on_enter(self, mock_display_class, mock_read_key) -> None:
        """Test returns text when Enter is pressed."""
        mock_display = MagicMock()
        mock_display_class.return_value = mock_display
        mock_read_key.return_value = "ENTER"

        editor = TextEditor("hello")
        result = editor.run()

        assert result == "hello"

    @patch("ami.cli_components.text_editor.read_key_sequence")
    @patch("ami.cli_components.text_editor.EditorDisplay")
    def test_returns_none_on_double_ctrl_c(
        self, mock_display_class, mock_read_key
    ) -> None:
        """Test returns None on double Ctrl+C with empty content."""
        mock_display = MagicMock()
        mock_display_class.return_value = mock_display

        # First call raises KeyboardInterrupt, then again
        mock_read_key.side_effect = [KeyboardInterrupt, KeyboardInterrupt]

        editor = TextEditor("")
        result = editor.run()

        assert result is None

    @patch("ami.cli_components.text_editor.read_key_sequence")
    @patch("ami.cli_components.text_editor.EditorDisplay")
    def test_clears_content_on_first_ctrl_c(
        self, mock_display_class, mock_read_key
    ) -> None:
        """Test clears content on first Ctrl+C with content."""
        mock_display = MagicMock()
        mock_display_class.return_value = mock_display

        # KeyboardInterrupt, then ENTER to exit
        mock_read_key.side_effect = [KeyboardInterrupt, "ENTER"]

        editor = TextEditor("some content")
        result = editor.run()

        # Content should be cleared, but then we exit with ENTER
        # So result should be the cleared content
        assert result == ""

    @patch("ami.cli_components.text_editor.read_key_sequence")
    @patch("ami.cli_components.text_editor.EditorDisplay")
    def test_handles_none_key(self, mock_display_class, mock_read_key) -> None:
        """Test handles None key sequence."""
        mock_display = MagicMock()
        mock_display_class.return_value = mock_display

        # None key, then ENTER to exit
        mock_read_key.side_effect = [None, "ENTER"]

        editor = TextEditor("hello")
        result = editor.run()

        assert result == "hello"

    @patch("ami.cli_components.text_editor.read_key_sequence")
    @patch("ami.cli_components.text_editor.EditorDisplay")
    def test_clears_display_on_submit(self, mock_display_class, mock_read_key) -> None:
        """Test clears display on submit when clear_on_submit=True."""
        mock_display = MagicMock()
        mock_display_class.return_value = mock_display
        mock_read_key.return_value = "ENTER"

        editor = TextEditor("hello")
        editor.run(clear_on_submit=True)

        mock_display.clear.assert_called_once()

    @patch("ami.cli_components.text_editor.read_key_sequence")
    @patch("ami.cli_components.text_editor.EditorDisplay")
    def test_does_not_clear_on_no_clear(
        self, mock_display_class, mock_read_key
    ) -> None:
        """Test does not clear display when clear_on_submit=False."""
        mock_display = MagicMock()
        mock_display_class.return_value = mock_display
        mock_read_key.return_value = "ENTER"

        editor = TextEditor("hello")
        editor.run(clear_on_submit=False)

        mock_display.clear.assert_not_called()

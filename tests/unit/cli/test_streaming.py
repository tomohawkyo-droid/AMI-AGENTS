"""Unit tests for ami/cli/streaming.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ami.cli.streaming import RendererObserver, execute_streaming
from ami.types.api import ProviderMetadata, StreamEventData
from ami.types.events import StreamEvent, StreamEventType


class TestRendererObserver:
    """Tests for RendererObserver class."""

    def test_init(self):
        """Test RendererObserver initialization."""
        renderer = MagicMock()
        processor = MagicMock()

        observer = RendererObserver(renderer, processor)

        assert observer.renderer is renderer
        assert observer.processor is processor

    def test_on_event_chunk(self):
        """Test on_event processes chunk events."""
        renderer = MagicMock()
        processor = MagicMock()
        observer = RendererObserver(renderer, processor)

        event = StreamEvent(type=StreamEventType.CHUNK, data="test chunk")
        observer.on_event(event)

        renderer.process_chunk.assert_called_once_with("test chunk")

    def test_on_event_metadata_with_session_id(self):
        """Test on_event processes metadata events with session_id."""
        renderer = MagicMock()
        processor = MagicMock()
        observer = RendererObserver(renderer, processor)

        metadata = ProviderMetadata(session_id="test-session")
        event_data = StreamEventData(output="", metadata=metadata)
        event = StreamEvent(type=StreamEventType.METADATA, data=event_data)
        observer.on_event(event)

        assert renderer.session_id == "test-session"

    def test_on_event_metadata_without_session_id(self):
        """Test on_event ignores metadata events without session_id."""
        renderer = MagicMock()
        renderer.session_id = "original"
        processor = MagicMock()
        observer = RendererObserver(renderer, processor)

        metadata = ProviderMetadata(session_id=None)
        event_data = StreamEventData(output="", metadata=metadata)
        event = StreamEvent(type=StreamEventType.METADATA, data=event_data)
        observer.on_event(event)

        # session_id should not be changed
        assert renderer.session_id == "original"

    def test_on_event_non_chunk_non_metadata(self):
        """Test on_event ignores other event types."""
        renderer = MagicMock()
        processor = MagicMock()
        observer = RendererObserver(renderer, processor)

        event = StreamEvent(type=StreamEventType.COMPLETE, data="complete")
        observer.on_event(event)

        renderer.process_chunk.assert_not_called()


class MockAgentConfig:
    """Mock AgentConfig for testing."""

    def __init__(
        self,
        timeout: int | None = None,
        enable_streaming: bool = False,
        session_id: str | None = None,
        capture_content: bool = False,
    ):
        self.timeout = timeout
        self.enable_streaming = enable_streaming
        self.session_id = session_id
        self.capture_content = capture_content


class TestExecuteStreaming:
    """Tests for execute_streaming function."""

    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_no_streaming(self, mock_processor_class):
        """Test execute_streaming without streaming enabled."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        metadata = ProviderMetadata(exit_code=0)
        event_data = StreamEventData(output="test output", metadata=metadata)
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        config = MockAgentConfig(enable_streaming=False)
        result_output, result_metadata = execute_streaming(
            ["echo", "test"], agent_config=config
        )

        assert result_output == "test output"
        assert result_metadata == metadata

    @patch("ami.cli.streaming.StreamRenderer")
    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_with_streaming(
        self, mock_processor_class, mock_renderer_class
    ):
        """Test execute_streaming with streaming enabled."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        mock_renderer = MagicMock()
        mock_renderer.finish.return_value = {}
        mock_renderer_class.return_value = mock_renderer

        metadata = ProviderMetadata(exit_code=0)
        event_data = StreamEventData(output="test output", metadata=metadata)
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        config = MockAgentConfig(enable_streaming=True, session_id="test-session")
        result_output, _result_metadata = execute_streaming(
            ["echo", "test"], agent_config=config
        )

        assert result_output == "test output"
        mock_renderer.start.assert_called_once()
        mock_renderer.finish.assert_called_once()
        mock_processor.add_observer.assert_called_once()

    @patch("ami.cli.streaming.StreamRenderer")
    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_with_session_id_from_renderer(
        self, mock_processor_class, mock_renderer_class
    ):
        """Test execute_streaming merges session_id from renderer."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        mock_renderer = MagicMock()
        mock_renderer.finish.return_value = {"session_id": "renderer-session"}
        mock_renderer_class.return_value = mock_renderer

        metadata = ProviderMetadata(exit_code=0)
        event_data = StreamEventData(output="test output", metadata=metadata)
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        config = MockAgentConfig(enable_streaming=True)
        _result_output, result_metadata = execute_streaming(
            ["echo", "test"], agent_config=config
        )

        assert result_metadata is not None
        assert result_metadata.session_id == "renderer-session"

    @patch("ami.cli.streaming.StreamRenderer")
    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_exception_finishes_renderer(
        self, mock_processor_class, mock_renderer_class
    ):
        """Test execute_streaming finishes renderer on exception."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        mock_processor.run.side_effect = Exception("Test error")
        mock_renderer = MagicMock()
        mock_renderer_class.return_value = mock_renderer

        config = MockAgentConfig(enable_streaming=True)

        with pytest.raises(Exception, match="Test error"):
            execute_streaming(["echo", "test"], agent_config=config)

        mock_renderer.finish.assert_called_once()

    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_no_config(self, mock_processor_class):
        """Test execute_streaming without agent config."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        metadata = ProviderMetadata(exit_code=0)
        event_data = StreamEventData(output="test output", metadata=metadata)
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        result_output, _result_metadata = execute_streaming(["echo", "test"])

        assert result_output == "test output"

    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_with_stdin(self, mock_processor_class):
        """Test execute_streaming passes stdin_data."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        metadata = ProviderMetadata(exit_code=0)
        event_data = StreamEventData(output="test output", metadata=metadata)
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        execute_streaming(["cat"], stdin_data="input data")

        mock_processor.run.assert_called_once_with(stdin_data="input data")

    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_with_cwd(self, mock_processor_class):
        """Test execute_streaming passes cwd."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        metadata = ProviderMetadata(exit_code=0)
        event_data = StreamEventData(output="", metadata=metadata)
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        cwd = Path("/tmp")
        execute_streaming(["ls"], cwd=cwd)

        mock_processor_class.assert_called_once()
        call_kwargs = mock_processor_class.call_args.kwargs
        assert call_kwargs["cwd"] == cwd

    @patch("ami.cli.streaming.StreamRenderer")
    @patch("ami.cli.streaming.StreamProcessor")
    def test_execute_streaming_no_metadata_from_complete_event(
        self, mock_processor_class, mock_renderer_class
    ):
        """Test execute_streaming handles None metadata."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        mock_renderer = MagicMock()
        mock_renderer.finish.return_value = {}
        mock_renderer_class.return_value = mock_renderer

        # Send a complete event where metadata is None would be replaced
        event_data = StreamEventData(output="test output", metadata=ProviderMetadata())
        complete_event = StreamEvent(type=StreamEventType.COMPLETE, data=event_data)
        mock_processor.run.return_value = [complete_event]

        config = MockAgentConfig(enable_streaming=True)
        result_output, result_metadata = execute_streaming(
            ["echo", "test"], agent_config=config
        )

        assert result_output == "test output"
        assert result_metadata is not None

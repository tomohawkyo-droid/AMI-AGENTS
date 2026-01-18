"""Unit tests for StreamProcessor."""

from unittest.mock import MagicMock, patch, call
import pytest
from ami.cli.stream_processor import StreamProcessor, StreamEvent
from ami.cli.exceptions import AgentTimeoutError

class TestStreamProcessor:
    
    @patch("ami.cli.stream_processor.start_streaming_process")
    @patch("ami.cli.stream_processor.read_streaming_line")
    def test_run_success(self, mock_read, mock_start):
        """Test successful execution with output chunks."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.wait.return_value = 0
        # Poll logic:
        # 1. read -> None. poll -> None (running).
        # 2. read -> None. poll -> 0 (done).
        # 3. finally block -> poll -> 0 (done).
        mock_process.poll.side_effect = [None, 0, 0]
        mock_start.return_value = mock_process
        
        # Simulate stream: chunk 1, chunk 2, EOF (continue), EOF (break)
        mock_read.side_effect = [
            ("chunk1", False),
            ("chunk2", False),
            (None, False),
            (None, False)
        ]
        
        processor = StreamProcessor(cmd=["echo", "test"])
        
        # Consume generator
        events = list(processor.run())
        
        # Verify events
        assert len(events) == 3 # chunk1, chunk2, complete
        assert events[0].type == "chunk"
        assert events[0].data == "chunk1"
        assert events[1].type == "chunk"
        assert events[1].data == "chunk2"
        assert events[2].type == "complete"
        assert events[2].data["output"] == "chunk1\nchunk2\n"
        assert events[2].data["metadata"]["exit_code"] == 0

    @patch("ami.cli.stream_processor.start_streaming_process")
    @patch("ami.cli.stream_processor.read_streaming_line")
    def test_run_with_observer(self, mock_read, mock_start):
        """Test that observers are notified."""
        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0, 0]
        mock_start.return_value = mock_process
        
        mock_observer = MagicMock()
        
        processor = StreamProcessor(cmd=["test"])
        processor.add_observer(mock_observer)
        
        # Force loop break by side effect on read
        mock_read.side_effect = [("data", False), (None, False), (None, False)]
        
        list(processor.run())
        
        assert mock_observer.on_event.called
        assert mock_observer.on_event.call_count >= 2 # chunk, complete

    @patch("ami.cli.stream_processor.start_streaming_process")
    @patch("ami.cli.stream_processor.read_streaming_line")
    def test_run_timeout(self, mock_read, mock_start):
        """Test timeout behavior."""
        mock_process = MagicMock()
        mock_start.return_value = mock_process
        
        # Simulate timeout
        mock_read.return_value = (None, True) 
        
        processor = StreamProcessor(cmd=["test"], timeout=0.1)
        
        with patch("time.time", side_effect=[0, 0.2, 0.3, 0.4]): # Start, Check 1 (timeout)
             with pytest.raises(AgentTimeoutError):
                 list(processor.run())

    @patch("ami.cli.stream_processor.start_streaming_process")
    @patch("ami.cli.stream_processor.read_streaming_line")
    def test_provider_parsing(self, mock_read, mock_start):
        """Test provider-specific parsing integration."""
        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0, 0]
        mock_start.return_value = mock_process
        
        # Raw line that provider will parse
        mock_read.side_effect = [
            ('{"type": "message", "text": "parsed"}', False),
            (None, False),
            (None, False)
        ]
        
        mock_provider = MagicMock()
        # Returns (text, metadata)
        mock_provider._parse_stream_message.return_value = ("parsed", {"msg_id": 1})
        
        processor = StreamProcessor(cmd=["test"], provider=mock_provider)
        
        events = list(processor.run())
        
        # Expect: metadata event, chunk event, complete event
        types = [e.type for e in events]
        assert "metadata" in types
        assert "chunk" in types
        
        # Check metadata content
        meta_event = next(e for e in events if e.type == "metadata")
        assert meta_event.data == {"msg_id": 1}
        
        # Check chunk content
        chunk_event = next(e for e in events if e.type == "chunk")
        assert chunk_event.data == "parsed"


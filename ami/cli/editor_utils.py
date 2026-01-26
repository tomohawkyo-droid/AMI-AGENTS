#!/usr/bin/env python3

import datetime
from pathlib import Path


def save_session_log(content: str) -> Path:
    """Save the content to a timestamped file in logs/ directory.

    Args:
        content: The text content to save.

    Returns:
        Path to the saved file.
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = logs_dir / f"text_input_{timestamp}.txt"

    # Save the content to the file
    with filename.open("w", encoding="utf-8") as f:
        f.write(content)

    return filename

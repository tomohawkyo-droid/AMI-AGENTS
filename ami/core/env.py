"""Environment setup for agent execution."""

import os
import sys
from pathlib import Path

# Setup import path for project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def setup_agent_env() -> None:
    """Ensure agent execution environment is correct."""
    # Environment setup is now handled externally (e.g. via .bashrc or container env)
    pass

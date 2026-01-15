"""Environment setup for agent execution."""

import os
import sys
from pathlib import Path

# Setup import path for project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def setup_agent_env() -> None:
    """Ensure agent execution environment (PATH, LD_LIBRARY_PATH) is correct."""
    boot_bin = PROJECT_ROOT / ".boot-linux" / "bin"
    boot_lib = PROJECT_ROOT / ".boot-linux" / "lib"
    
    # Prepend to PATH
    if str(boot_bin) not in os.environ["PATH"]:
        os.environ["PATH"] = f"{boot_bin}:{os.environ['PATH']}"
        
    # Prepend to LD_LIBRARY_PATH
    current_ld = os.environ.get("LD_LIBRARY_PATH", "")
    if str(boot_lib) not in current_ld:
        os.environ["LD_LIBRARY_PATH"] = f"{boot_lib}:{current_ld}"

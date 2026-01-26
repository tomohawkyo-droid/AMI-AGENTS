"""End-to-end performance test for Qwen CLI agent.

Measures response time and memory footprint with progressively larger prompts.
"""

import contextlib
import shutil
import subprocess
import time
from pathlib import Path

import psutil
import pytest

from ami.cli.provider_type import ProviderType
from ami.core.config import get_config

# Constants
TRANSCRIPT_SOURCE = Path("uv.lock")
PERFORMANCE_TEST_TIMEOUT_SECONDS = 180
SIZES = [
    1000,
    5000,
    10000,
]  # Characters - larger sizes may timeout depending on backend speed
AGENT_CMD = ["./ami-agent", "--query"]


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


def get_process_memory(proc_pid: int) -> int:
    """Get total RSS memory of process and its children."""
    try:
        parent = psutil.Process(proc_pid)
        children = parent.children(recursive=True)
        total_rss = parent.memory_info().rss
        for child in children:
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                total_rss += child.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0
    else:
        return total_rss


@pytest.mark.e2e
def test_performance_scaling() -> None:
    if not TRANSCRIPT_SOURCE.exists():
        pytest.xfail(f"Transcript source not found: {TRANSCRIPT_SOURCE}")

    config = get_config()
    qwen_cmd = config.get_provider_command(ProviderType.QWEN)

    # Check if executable exists
    script_dir = _find_project_root()
    cmd_path = (
        script_dir / qwen_cmd if not Path(qwen_cmd).is_absolute() else Path(qwen_cmd)
    )

    if not cmd_path.exists() and not shutil.which(qwen_cmd):
        pytest.xfail(f"qwen binary not found at {cmd_path} or in PATH")

    full_content = TRANSCRIPT_SOURCE.read_text(errors="replace")
    print(f"Content length: {len(full_content)}")

    print("\n\n=== Performance Test Results ===")
    print(f"{'Size (chars)':<15} | {'Time (s)':<10} | {'Peak Mem (MB)':<15}")
    print("-" * 46)

    for size in SIZES:
        print(f"Testing size {size}...")
        if size > len(full_content):
            print(f"Skipping size {size} (content too short)")
            continue

        prompt_content = full_content[:size]
        # Using --query with the full text. The QwenAgentCLI should now handle this
        # by passing it via stdin, avoiding shell/process arg limits/hangs.
        prompt_text = f"Please analyze this transcript segment and summarize key events:\n\n{prompt_content}"

        start_time = time.time()

        try:
            # Launch agent with --query
            # We don't need to use temp file anymore if QwenAgentCLI works correctly
            process = subprocess.Popen(
                [*AGENT_CMD, prompt_text],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            peak_memory = 0

            # Monitor loop
            while process.poll() is None:
                current_mem = get_process_memory(process.pid)
                peak_memory = max(peak_memory, current_mem)
                time.sleep(0.1)

                # Timeout safety
                if time.time() - start_time > PERFORMANCE_TEST_TIMEOUT_SECONDS:
                    process.kill()
                    pytest.fail(f"Timeout at size {size}")

            duration = time.time() - start_time
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                print(f"Error at size {size}:")
                print(f"STDOUT:\n{stdout}")
                print(f"STDERR:\n{stderr}")
                pytest.fail(f"Agent failed at size {size}")

            peak_mb = peak_memory / (1024 * 1024)
            print(f"{size:<15} | {duration:<10.2f} | {peak_mb:<15.2f}")

        except Exception as e:
            pytest.fail(f"Execution error: {e}")

    print("================================")


if __name__ == "__main__":
    test_performance_scaling()

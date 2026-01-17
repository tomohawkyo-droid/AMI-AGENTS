"""End-to-end performance test for Qwen CLI agent.

Measures response time and memory footprint with progressively larger prompts.
"""

import time
import psutil
import subprocess
import shutil
import os
import tempfile
from pathlib import Path
import pytest

from ami.core.config import get_config

# Constants
TRANSCRIPT_SOURCE = Path("uv.lock")
SIZES = [1000, 5000, 10000]  # Characters - larger sizes may timeout depending on backend speed
AGENT_CMD = ["./ami-agent", "--query"]

def get_process_memory(proc_pid):
    """Get total RSS memory of process and its children."""
    try:
        parent = psutil.Process(proc_pid)
        children = parent.children(recursive=True)
        total_rss = parent.memory_info().rss
        for child in children:
            try:
                total_rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return total_rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0

@pytest.mark.e2e
def test_performance_scaling():
    if not TRANSCRIPT_SOURCE.exists():
        pytest.skip(f"Transcript source not found: {TRANSCRIPT_SOURCE}")

    config = get_config()
    from ami.cli.provider_type import ProviderType
    qwen_cmd = config.get_provider_command(ProviderType.QWEN)
    
    # Check if executable exists
    # Use SCRIPT_DIR to resolve relative paths
    script_dir = Path(__file__).resolve().parents[2]
    cmd_path = script_dir / qwen_cmd if not Path(qwen_cmd).is_absolute() else Path(qwen_cmd)
    
    if not cmd_path.exists() and not shutil.which(qwen_cmd):
        pytest.skip(f"qwen binary not found at {cmd_path} or in PATH")

    full_content = TRANSCRIPT_SOURCE.read_text(errors='replace')
    print(f"Content length: {len(full_content)}")
    
    print("\n\n=== Performance Test Results ===")
    print(f"{ 'Size (chars)':<15} | { 'Time (s)':<10} | { 'Peak Mem (MB)':<15}")
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
                AGENT_CMD + [prompt_text],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
    
            peak_memory = 0
    
            # Monitor loop
            while process.poll() is None:
                current_mem = get_process_memory(process.pid)
                peak_memory = max(peak_memory, current_mem)
                time.sleep(0.1)
    
                # Timeout safety
                if time.time() - start_time > 180:
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
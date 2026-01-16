"""Process execution utilities for AMI Agents.

Provides robust subprocess management using file-based I/O to avoid pipe buffer deadlocks.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ProcessExecutor:
    """Synchronous process executor using file-based I/O for robustness."""

    def __init__(self, work_dir: Optional[Path] = None):
        self.work_dir = work_dir or Path.cwd()

    def run(
        self,
        command: Union[str, List[str]],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run a command and capture output via temporary files.

        Args:
            command: Command string or list of arguments.
            cwd: Working directory (defaults to self.work_dir).
            env: Environment variables (defaults to os.environ).
            timeout: Execution timeout in seconds.

        Returns:
            Dict containing 'stdout', 'stderr', 'returncode'.
        """
        # Resolve working directory
        cwd = cwd or self.work_dir
        if not cwd.exists():
            return {
                "stdout": "",
                "stderr": f"Working directory does not exist: {cwd}",
                "returncode": 1
            }

        # Prepare environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        # Create temporary files for stdout/stderr
        # Using tempfile.TemporaryFile is safer than managing paths manually
        # as it handles cleanup automatically on close.
        with tempfile.TemporaryFile(mode='w+') as stdout_f, \
             tempfile.TemporaryFile(mode='w+') as stderr_f:
            
            try:
                # Normalize command to list if string (shell=True handling)
                shell_mode = isinstance(command, str)
                
                process = subprocess.Popen(
                    command,
                    cwd=str(cwd),
                    env=run_env,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    shell=shell_mode,
                    text=True
                )

                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    return {
                        "stdout": self._read_file(stdout_f),
                        "stderr": f"Process timed out after {timeout} seconds.\n" + self._read_file(stderr_f),
                        "returncode": 124  # Standard timeout exit code
                    }

                return {
                    "stdout": self._read_file(stdout_f),
                    "stderr": self._read_file(stderr_f),
                    "returncode": process.returncode
                }

            except Exception as e:
                return {
                    "stdout": "",
                    "stderr": f"Execution failed: {str(e)}",
                    "returncode": 1
                }

    def _read_file(self, f: Any) -> str:
        """Read content from a temporary file object."""
        f.seek(0)
        return f.read().strip()

"""Process execution utilities for AMI Agents.

Provides robust subprocess management using memory-based pipes and selectors
to avoid deadlocks and minimize disk I/O.
"""

import os
import selectors
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ProcessExecutor:
    """Synchronous process executor using memory-based pipes and selectors."""

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
        Run a command and capture output via pipes.

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

        # Normalize command to list if string (shell=True handling)
        shell_mode = isinstance(command, str)
        
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=run_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell_mode,
                text=True,
                bufsize=1,  # Line buffered
            )

            stdout_data = []
            stderr_data = []
            
            # Use selectors to read from both pipes concurrently without deadlocks
            sel = selectors.DefaultSelector()
            if process.stdout:
                sel.register(process.stdout, selectors.EVENT_READ, stdout_data)
            if process.stderr:
                sel.register(process.stderr, selectors.EVENT_READ, stderr_data)

            start_time = time.time()
            while sel.get_map():
                # Check timeout
                if timeout is not None and (time.time() - start_time) > timeout:
                    process.kill()
                    process.wait()
                    sel.close()
                    return {
                        "stdout": "".join(stdout_data).strip(),
                        "stderr": f"Process timed out after {timeout} seconds.\n" + "".join(stderr_data).strip(),
                        "returncode": 124
                    }

                # Wait for data with short timeout to allow loop to check process status
                events = sel.select(timeout=0.1)
                for key, _ in events:
                    if hasattr(key.fileobj, 'readline'):
                        # fileobj is a pipe (text mode)
                        line = key.fileobj.readline()
                        if line:
                            key.data.append(line)
                        else:
                            # EOF
                            sel.unregister(key.fileobj)
                
                # If no events but process finished, ensure we close pipes
                if not events and process.poll() is not None:
                    # Final drain
                    for key in list(sel.get_map().values()):
                        line = key.fileobj.read()
                        if line:
                            key.data.append(line)
                        sel.unregister(key.fileobj)
            
            sel.close()
            process.wait()

            return {
                "stdout": "".join(stdout_data).strip(),
                "stderr": "".join(stderr_data).strip(),
                "returncode": process.returncode
            }

        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution failed: {str(e)}",
                "returncode": 1
            }
"""Bootstrap component models, detection, and version checking."""

import re
import subprocess
from enum import Enum

from pydantic import BaseModel

from ami.core.env import PROJECT_ROOT

__all__ = [
    "PROJECT_ROOT",
    "Component",
    "ComponentStatus",
    "ComponentType",
    "GroupComponents",
]


class ComponentType(Enum):
    """Type of component installation."""

    SCRIPT = "script"
    UV = "uv"


class ComponentStatus(BaseModel):
    installed: bool
    version: str | None = None
    path: str | None = None


class GroupComponents(BaseModel):
    group: str
    components: list["Component"] = []


class Component(BaseModel):
    name: str
    label: str
    description: str
    type: ComponentType
    group: str

    package: str | None = None
    script: str | None = None

    detect_cmd: list[str] | None = None
    detect_path: str | None = None
    version_pattern: str | None = None
    version_cmd: list[str] | None = None

    def get_status(self) -> ComponentStatus:
        """Check if component is installed and get version."""
        if self.detect_path:
            path = PROJECT_ROOT / self.detect_path
            if path.exists():
                version = self._get_version_from_cmd() if self.version_cmd else None
                return ComponentStatus(installed=True, version=version, path=str(path))

        if self.detect_cmd:
            try:
                result = subprocess.run(
                    self.detect_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=str(PROJECT_ROOT),
                    check=False,
                )
                if result.returncode == 0:
                    version = self._extract_version(result.stdout + result.stderr)
                    return ComponentStatus(installed=True, version=version)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        return ComponentStatus(installed=False)

    def _get_version_from_cmd(self) -> str | None:
        """Get version using version command."""
        if not self.version_cmd:
            return None
        try:
            result = subprocess.run(
                self.version_cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(PROJECT_ROOT),
                check=False,
            )
            if result.returncode == 0:
                return self._extract_version(result.stdout + result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None

    def _extract_version(self, output: str) -> str | None:
        """Extract version from command output."""
        if not output:
            return None

        if self.version_pattern:
            match = re.search(self.version_pattern, output)
            if match:
                return match.group(1) if match.groups() else match.group(0)

        patterns = [
            r"(\d+\.\d+\.\d+)",
            r"v(\d+\.\d+\.\d+)",
            r"(\d+\.\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)

        return None

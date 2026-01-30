"""
Bootstrap component definitions with detection and version checking.

Each component defines:
- How to detect if it's installed
- How to get its version
- How to install it
"""

import re
import subprocess
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    msg = "Could not find project root"
    raise RuntimeError(msg)


PROJECT_ROOT = _find_project_root()


class ComponentType(Enum):
    """Type of component installation."""

    NPM = "npm"
    SCRIPT = "script"
    UV = "uv"  # Python packages via uv


class ComponentStatus(BaseModel):
    """Status of a component."""

    installed: bool
    version: str | None = None
    path: str | None = None


class Component(BaseModel):
    """A bootstrap component with detection capabilities."""

    name: str
    label: str
    description: str
    type: ComponentType
    group: str

    # Installation info
    package: str | None = None  # For npm packages
    script: str | None = None  # For script-based installs

    # Detection
    detect_cmd: list[str] | None = None  # Command to run for detection
    detect_path: str | None = None  # Path to check (relative to PROJECT_ROOT)
    version_pattern: str | None = None  # Regex to extract version from output
    version_cmd: list[str] | None = (
        None  # Command to get version (if different from detect)
    )

    def get_status(self) -> ComponentStatus:
        """Check if component is installed and get version."""
        # Try path-based detection first
        if self.detect_path:
            path = PROJECT_ROOT / self.detect_path
            if path.exists():
                version = self._get_version_from_cmd() if self.version_cmd else None
                return ComponentStatus(installed=True, version=version, path=str(path))

        # Try command-based detection
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

        # Default: try common version patterns
        patterns = [
            r"(\d+\.\d+\.\d+)",  # semver
            r"v(\d+\.\d+\.\d+)",  # v-prefixed semver
            r"(\d+\.\d+)",  # major.minor
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)

        return None


# =============================================================================
# Component Definitions
# =============================================================================

# Core Dependencies (installed FIRST, before anything else)
CORE_DEPS = [
    Component(
        name="uv",
        label="uv",
        description="Python package manager",
        type=ComponentType.SCRIPT,
        group="Core Dependencies",
        script="bootstrap_uv.sh",
        detect_path=".boot-linux/bin/uv",
        version_cmd=[".boot-linux/bin/uv", "--version"],
        version_pattern=r"uv (\d+\.\d+\.\d+)",
    ),
    Component(
        name="python",
        label="Python",
        description="Python venv for .boot-linux",
        type=ComponentType.SCRIPT,
        group="Core Dependencies",
        script="bootstrap_python.sh",
        detect_path=".boot-linux/bin/python",
        version_cmd=[".boot-linux/bin/python", "--version"],
        version_pattern=r"Python (\d+\.\d+\.\d+)",
    ),
]


def _npm_detect_path(package_name: str) -> str:
    """Get detection path for npm package."""
    # npm packages are installed in .venv/node_modules
    return f".venv/node_modules/{package_name}"


def _npm_version_cmd(package_name: str) -> list[str]:
    """Get version command for npm package."""
    return [
        "node",
        "-e",
        f"console.log(require('{package_name}/package.json').version)",
    ]


# AI Coding Assistants
AI_AGENTS = [
    Component(
        name="claude",
        label="Claude Code",
        description="Anthropic AI assistant",
        type=ComponentType.NPM,
        group="AI Coding Assistants",
        package="@anthropic-ai/claude-code@2.1.19",
        detect_path=_npm_detect_path("@anthropic-ai/claude-code"),
        version_cmd=[".venv/node_modules/.bin/claude", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
    Component(
        name="gemini",
        label="Gemini CLI",
        description="Google AI assistant",
        type=ComponentType.NPM,
        group="AI Coding Assistants",
        package="@google/gemini-cli@0.23.0",
        detect_path=_npm_detect_path("@google/gemini-cli"),
        version_cmd=[".venv/node_modules/.bin/gemini", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
    Component(
        name="qwen",
        label="Qwen Code",
        description="Alibaba AI assistant",
        type=ComponentType.NPM,
        group="AI Coding Assistants",
        package="@qwen-code/qwen-code@0.6.2",
        detect_path=_npm_detect_path("@qwen-code/qwen-code"),
        version_cmd=[".venv/node_modules/.bin/qwen", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
]

# Containers & Orchestration
CONTAINERS = [
    Component(
        name="podman",
        label="Podman",
        description="Container runtime",
        type=ComponentType.SCRIPT,
        group="Containers & Orchestration",
        script="bootstrap_podman.sh",
        detect_path=".boot-linux/bin/podman",
        version_cmd=[".boot-linux/bin/podman", "--version"],
        version_pattern=r"podman version (\d+\.\d+\.\d+)",
    ),
    Component(
        name="kubernetes",
        label="Kubernetes",
        description="k8s tools (kubectl, helm)",
        type=ComponentType.SCRIPT,
        group="Containers & Orchestration",
        script="bootstrap_kubernetes.sh",
        detect_path=".boot-linux/bin/kubectl",
        version_cmd=[".boot-linux/bin/kubectl", "version", "--client", "-o", "json"],
        version_pattern=r'"gitVersion":\s*"v?(\d+\.\d+\.\d+)"',
    ),
]

# Development Tools
DEV_TOOLS = [
    Component(
        name="git",
        label="Git",
        description="Version control",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_git.sh",
        detect_path=".boot-linux/git/bin/git",
        version_cmd=[".boot-linux/git/bin/git", "--version"],
        version_pattern=r"git version (\d+\.\d+\.\d+)",
    ),
    Component(
        name="go",
        label="Go",
        description="Go language",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_go.sh",
        detect_path=".boot-linux/go/bin/go",
        version_cmd=[".boot-linux/go/bin/go", "version"],
        version_pattern=r"go(\d+\.\d+\.\d+)",
    ),
    Component(
        name="sd",
        label="sd",
        description="sed alternative",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_sd.sh",
        detect_path=".boot-linux/bin/sd",
        version_cmd=[".boot-linux/bin/sd", "--version"],
        version_pattern=r"sd (\d+\.\d+\.\d+)",
    ),
]

# Security & Networking
SECURITY = [
    Component(
        name="openssh",
        label="OpenSSH",
        description="SSH tools",
        type=ComponentType.SCRIPT,
        group="Security & Networking",
        script="bootstrap_openssh.sh",
        detect_path=".venv/openssh/sbin/sshd",
        version_cmd=[".venv/openssh/sbin/sshd", "-V"],
        version_pattern=r"OpenSSH[_\s](\d+\.\d+)",
    ),
    Component(
        name="openssl",
        label="OpenSSL",
        description="SSL/TLS toolkit",
        type=ComponentType.SCRIPT,
        group="Security & Networking",
        script="bootstrap_openssl.sh",
        detect_path=".boot-linux/bin/openssl",
        version_cmd=[".boot-linux/bin/openssl", "version"],
        version_pattern=r"OpenSSL (\d+\.\d+\.\d+)",
    ),
    Component(
        name="openvpn",
        label="OpenVPN",
        description="VPN client",
        type=ComponentType.SCRIPT,
        group="Security & Networking",
        script="bootstrap_openvpn.sh",
        detect_path=".boot-linux/bin/openvpn",
        version_cmd=[".boot-linux/openvpn/sbin/openvpn", "--version"],
        version_pattern=r"OpenVPN (\d+\.\d+\.\d+)",
    ),
    Component(
        name="cloudflared",
        label="Cloudflared",
        description="CF tunnel client",
        type=ComponentType.SCRIPT,
        group="Security & Networking",
        script="bootstrap_cloudflared.sh",
        detect_path=".boot-linux/bin/cloudflared",
        version_cmd=[".boot-linux/bin/cloudflared", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
]

# Document Processing
DOCUMENTS = [
    Component(
        name="pandoc",
        label="Pandoc",
        description="Document converter",
        type=ComponentType.SCRIPT,
        group="Document Processing",
        script="bootstrap_pandoc.sh",
        detect_path=".boot-linux/bin/pandoc",
        version_cmd=[".boot-linux/bin/pandoc", "--version"],
        version_pattern=r"pandoc (\d+\.\d+\.\d+)",
    ),
    Component(
        name="texlive",
        label="TeX Live",
        description="LaTeX distribution",
        type=ComponentType.SCRIPT,
        group="Document Processing",
        script="bootstrap_texlive.sh",
        detect_path=".boot-linux/texlive",
        detect_cmd=[".boot-linux/bin/pdflatex", "--version"],
        version_pattern=r"pdfTeX (\d+\.\d+)",
    ),
    Component(
        name="pdfjam",
        label="PDFjam",
        description="PDF manipulation",
        type=ComponentType.SCRIPT,
        group="Document Processing",
        script="bootstrap_pdfjam.sh",
        detect_path=".boot-linux/bin/pdfjam",
        version_cmd=[".boot-linux/bin/pdfjam", "--version"],
        version_pattern=r"pdfjam (\d+\.\d+)",
    ),
    Component(
        name="wkhtmltopdf",
        label="wkhtmltopdf",
        description="HTML to PDF",
        type=ComponentType.SCRIPT,
        group="Document Processing",
        script="bootstrap_wkhtmltopdf.sh",
        detect_path=".boot-linux/bin/wkhtmltopdf",
        version_cmd=[".boot-linux/bin/wkhtmltopdf", "--version"],
        version_pattern=r"wkhtmltopdf (\d+\.\d+\.\d+)",
    ),
]

# Matrix & Communication
MATRIX = [
    Component(
        name="matrix_commander",
        label="Matrix Cmdr",
        description="Matrix CLI client",
        type=ComponentType.SCRIPT,
        group="Matrix & Communication",
        script="bootstrap_matrix_commander.sh",
        detect_cmd=[".boot-linux/bin/python", "-m", "matrix_commander", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
    Component(
        name="synadm",
        label="Synadm",
        description="Synapse admin CLI",
        type=ComponentType.SCRIPT,
        group="Matrix & Communication",
        script="bootstrap_synadm.sh",
        detect_path=".boot-linux/bin/synadm",
        version_cmd=[".boot-linux/bin/synadm", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
]

# Miscellaneous
MISC = [
    Component(
        name="adb",
        label="ADB",
        description="Android Debug Bridge",
        type=ComponentType.SCRIPT,
        group="Miscellaneous",
        script="bootstrap_adb.sh",
        detect_path=".boot-linux/bin/adb",
        version_cmd=[".boot-linux/bin/adb", "--version"],
        version_pattern=r"Android Debug Bridge version (\d+\.\d+\.\d+)",
    ),
    Component(
        name="ansible",
        label="Ansible",
        description="IT automation",
        type=ComponentType.SCRIPT,
        group="Miscellaneous",
        script="bootstrap_ansible.sh",
        detect_cmd=["uv", "run", "ansible", "--version"],
        version_pattern=r"ansible.*?(\d+\.\d+\.\d+)",
    ),
]

# All components grouped (CORE_DEPS first for installation order)
ALL_COMPONENTS: list[Component] = [
    *CORE_DEPS,
    *AI_AGENTS,
    *CONTAINERS,
    *DEV_TOOLS,
    *SECURITY,
    *DOCUMENTS,
    *MATRIX,
    *MISC,
]

# Group names in order (Core Dependencies first)
GROUPS = [
    "Core Dependencies",
    "AI Coding Assistants",
    "Containers & Orchestration",
    "Development Tools",
    "Security & Networking",
    "Document Processing",
    "Matrix & Communication",
    "Miscellaneous",
]


def get_components_by_group() -> dict:
    """Get components organized by group.

    Returns a dict mapping group name to list of Component.
    """
    result: dict = {g: [] for g in GROUPS}
    for comp in ALL_COMPONENTS:
        if comp.group in result:
            result[comp.group].append(comp)
    return result


def get_component_by_name(name: str) -> Component | None:
    """Get a component by its name."""
    for comp in ALL_COMPONENTS:
        if comp.name == name:
            return comp
    return None

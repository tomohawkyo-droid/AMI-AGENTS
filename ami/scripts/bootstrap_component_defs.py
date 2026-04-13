"""Bootstrap component data definitions and query functions.

Component model lives in bootstrap_components.py (Layer 1).
This file is Layer 2: data + functions that operate on data.
Dependency direction: this file -> bootstrap_components, never reverse.
"""

import json

from ami.core.env import PROJECT_ROOT
from ami.scripts.bootstrap_components import (
    Component,
    ComponentType,
    GroupComponents,
)


def _get_package_version(package_name: str) -> str:
    """Get package version from scripts/package.json."""
    pkg_json_path = PROJECT_ROOT / "scripts/package.json"
    if not pkg_json_path.exists():
        return "latest"

    try:
        with open(pkg_json_path) as f:
            data = json.load(f)
            version = data.get("dependencies", {}).get(package_name, "latest")
            return str(version)
    except Exception:
        return "latest"


# Core Dependencies (installed FIRST, before anything else)
# Note: git, openssh, openssl, openvpn are system dependencies checked by pre-req.sh
# They are NOT bootstrap components — install them via: sudo make pre-req
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
        detect_path=".boot-linux/python-env/bin/python",
        version_cmd=[".boot-linux/bin/python", "--version"],
        version_pattern=r"Python (\d+\.\d+\.\d+)",
    ),
    Component(
        name="gcc",
        label="GCC/musl",
        description="C compiler (static toolchain)",
        type=ComponentType.SCRIPT,
        group="Core Dependencies",
        script="bootstrap_gcc.sh",
        detect_path=".boot-linux/bin/gcc",
        version_cmd=[".boot-linux/bin/gcc", "--version"],
        version_pattern=r"gcc.*?(\d+\.\d+\.\d+)",
    ),
    Component(
        name="git_xet",
        label="Git Xet",
        description="HuggingFace large file storage",
        type=ComponentType.SCRIPT,
        group="Core Dependencies",
        script="bootstrap_git_xet.sh",
        detect_path=".boot-linux/bin/git-lfs",
        version_cmd=[".boot-linux/bin/git-lfs", "--version"],
        version_pattern=r"git-lfs/(\d+\.\d+\.\d+)",
    ),
]

# AI Coding Assistants
AI_AGENTS = [
    Component(
        name="claude",
        label="Claude Code",
        description="Anthropic AI assistant",
        type=ComponentType.SCRIPT,
        group="AI Coding Assistants",
        script="bootstrap_agents.sh",
        package=f"@anthropic-ai/claude-code@{_get_package_version('@anthropic-ai/claude-code')}",
        detect_path=".venv/node_modules/@anthropic-ai/claude-code",
        version_cmd=[".venv/node_modules/.bin/claude", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
    Component(
        name="gemini",
        label="Gemini CLI",
        description="Google AI assistant",
        type=ComponentType.SCRIPT,
        group="AI Coding Assistants",
        script="bootstrap_agents.sh",
        package=f"@google/gemini-cli@{_get_package_version('@google/gemini-cli')}",
        detect_path=".venv/node_modules/@google/gemini-cli",
        version_cmd=[".venv/node_modules/.bin/gemini", "--version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
    Component(
        name="qwen",
        label="Qwen Code",
        description="Alibaba AI assistant",
        type=ComponentType.SCRIPT,
        group="AI Coding Assistants",
        script="bootstrap_agents.sh",
        package=f"@qwen-code/qwen-code@{_get_package_version('@qwen-code/qwen-code')}",
        detect_path=".venv/node_modules/@qwen-code/qwen-code",
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
        version_cmd=[
            ".boot-linux/bin/kubectl",
            "version",
            "--client",
            "-o",
            "json",
        ],
        version_pattern=r'"gitVersion":\s*"v?(\d+\.\d+\.\d+)"',
    ),
]

# Development Tools
DEV_TOOLS = [
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
        name="rust",
        label="Rust",
        description="Rust language & Cargo",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_rust.sh",
        detect_path=".boot-linux/rust/bin/cargo",
        version_cmd=["ami/scripts/bin/ami-run", "rustc", "--version"],
        version_pattern=r"rustc (\d+\.\d+\.\d+)",
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
    Component(
        name="gcloud",
        label="Google Cloud CLI",
        description="Google Cloud SDK (gcloud)",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_gcloud.sh",
        detect_path=".boot-linux/bin/ami-gcloud",
        version_cmd=[
            ".gcloud/google-cloud-sdk/bin/gcloud",
            "version",
            "--format=value(Google Cloud SDK)",
        ],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
    Component(
        name="gh",
        label="GitHub CLI",
        description="GitHub API client",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_gh.sh",
        detect_path=".boot-linux/bin/gh",
        version_cmd=[".boot-linux/bin/gh", "--version"],
        version_pattern=r"gh version (\d+\.\d+\.\d+)",
    ),
    Component(
        name="huggingface",
        label="HuggingFace CLI",
        description="HuggingFace Hub client",
        type=ComponentType.SCRIPT,
        group="Development Tools",
        script="bootstrap_hf.sh",
        detect_path=".boot-linux/python-env/bin/hf",
        version_cmd=[".boot-linux/python-env/bin/hf", "version"],
        version_pattern=r"(\d+\.\d+\.\d+)",
    ),
]

# Security & Networking
# Note: openssh, openssl, openvpn are system dependencies checked by pre-req.sh
SECURITY = [
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
        detect_path=".boot-linux/python-env/bin/matrix-commander",
        version_cmd=[
            ".boot-linux/python-env/bin/matrix-commander",
            "--version",
        ],
        version_pattern=r"matrix-commander: (\d+\.\d+\.\d+)",
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
        detect_path=".boot-linux/python-env/bin/ansible",
        version_cmd=[".boot-linux/python-env/bin/ansible", "--version"],
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


def get_components_by_group() -> list[GroupComponents]:
    """Get components organized by group."""
    groups_map = {g: GroupComponents(group=g, components=[]) for g in GROUPS}
    for comp in ALL_COMPONENTS:
        if comp.group in groups_map:
            groups_map[comp.group].components.append(comp)
    return list(groups_map.values())


def get_component_by_name(name: str) -> Component | None:
    """Get a component by its name."""
    for comp in ALL_COMPONENTS:
        if comp.name == name:
            return comp
    return None

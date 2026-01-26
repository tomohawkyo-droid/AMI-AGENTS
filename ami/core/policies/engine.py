"""Unified Policy Engine for AMI Agent security and quality guards.

Centralizes the loading and management of YAML-based policies and patterns.
"""

from pathlib import Path
from typing import TypedDict

import yaml

from ami.core.config import get_config


class PythonPattern(TypedDict):
    """Pattern definition for Python validation."""

    name: str
    pattern: str
    reason: str


# YAML manifest structure - can contain nested dicts of str or Path values
ManifestData = dict[str, str | dict[str, str | dict[str, str]]]


class PolicyEngine:
    """Manages system-wide policies and pattern validation rules."""

    def __init__(self, root_dir: Path | None = None):
        self.config = get_config()
        self.root = root_dir or self.config.root
        self.manifest_path = self.root / "ami/config/policies/manifest.yaml"
        self._manifest = self._load_manifest()
        # Instance-level caches to avoid lru_cache on methods
        self._bash_cache: dict[str, list[dict[str, str]]] = {}
        self._python_cache: list[PythonPattern] | None = None
        self._sensitive_cache: list[dict[str, str]] | None = None
        self._communication_cache: list[dict[str, str]] | None = None
        self._api_limit_cache: list[str] | None = None
        self._exemptions_cache: set[str] | None = None

    def _load_manifest(self) -> ManifestData:
        """Load the policy manifest."""
        if not self.manifest_path.exists():
            return {}
        with self.manifest_path.open() as f:
            result = yaml.safe_load(f)
            return result if isinstance(result, dict) else {}

    def _get_policy_path(self, *keys: str) -> Path | None:
        """Get policy path from manifest using dot-notation keys."""
        policies = self._manifest.get("policies")
        if not isinstance(policies, dict):
            return None

        current: object = policies
        for k in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(k)
            if current is None:
                return None
            if isinstance(current, str):
                return self.root / current

        # If we exhausted keys and ended with a string
        if isinstance(current, str):
            return self.root / current
        return None

    def load_bash_patterns(self, name: str = "default") -> list[dict[str, str]]:
        """Load Bash command validation patterns."""
        if name in self._bash_cache:
            return self._bash_cache[name]

        path = self._get_policy_path("bash", name)
        if not path or not path.exists():
            self._bash_cache[name] = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns: list[dict[str, str]] = (
            data.get("deny_patterns", []) if isinstance(data, dict) else []
        )
        self._bash_cache[name] = patterns
        return patterns

    def load_python_patterns(self) -> list[PythonPattern]:
        """Load Python fast pattern validation rules."""
        if self._python_cache is not None:
            return self._python_cache

        path = self._get_policy_path("python", "fast")
        if not path or not path.exists():
            self._python_cache = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns: list[PythonPattern] = (
            data.get("patterns", []) if isinstance(data, dict) else []
        )
        self._python_cache = patterns
        return patterns

    def load_sensitive_patterns(self) -> list[dict[str, str]]:
        """Load sensitive file patterns."""
        if self._sensitive_cache is not None:
            return self._sensitive_cache

        path = self._get_policy_path("sensitive", "files")
        if not path or not path.exists():
            self._sensitive_cache = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns: list[dict[str, str]] = (
            data.get("sensitive_patterns", []) if isinstance(data, dict) else []
        )
        self._sensitive_cache = patterns
        return patterns

    def load_communication_patterns(self) -> list[dict[str, str]]:
        """Load prohibited communication patterns."""
        if self._communication_cache is not None:
            return self._communication_cache

        path = self._get_policy_path("communication", "prohibited")
        if not path or not path.exists():
            self._communication_cache = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns: list[dict[str, str]] = (
            data.get("prohibited_patterns", []) if isinstance(data, dict) else []
        )
        self._communication_cache = patterns
        return patterns

    def load_api_limit_patterns(self) -> list[str]:
        """Load API limit patterns."""
        if self._api_limit_cache is not None:
            return self._api_limit_cache

        path = self._get_policy_path("api_limits", "files")
        if not path or not path.exists():
            self._api_limit_cache = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        self._api_limit_cache = [
            p.get("pattern") for p in data.get("api_limit_patterns", [])
        ]
        return self._api_limit_cache

    def load_exemptions(self) -> set[str]:
        """Load file exemptions for pattern checks."""
        if self._exemptions_cache is not None:
            return self._exemptions_cache

        path = self._get_policy_path("exemptions", "files")
        if not path or not path.exists():
            self._exemptions_cache = set()
            return set()

        with path.open() as f:
            data = yaml.safe_load(f)
        self._exemptions_cache = set(data.get("pattern_check_exemptions", []))
        return self._exemptions_cache


# Global singleton container (using dict to avoid global statement)
_singleton: dict[str, PolicyEngine] = {}


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance."""
    if "engine" not in _singleton:
        _singleton["engine"] = PolicyEngine()
    return _singleton["engine"]

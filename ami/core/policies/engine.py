"""Unified Policy Engine for AMI Agent security and quality guards.

Centralizes the loading and management of YAML-based policies and patterns.
"""

from pathlib import Path
from typing import NamedTuple, TypedDict

import yaml

from ami.core.config import get_config


class PythonPattern(TypedDict):
    """Pattern definition for Python validation."""

    name: str
    pattern: str
    reason: str


class BashPattern(TypedDict):
    """Pattern definition for Bash validation."""

    pattern: str
    reason: str


ManifestData = object  # YAML parsed data, structure validated at runtime


class BashCacheEntry(NamedTuple):
    """Cached bash patterns for a policy name."""

    name: str
    patterns: list[BashPattern]


class PolicyEngine:
    """Manages system-wide policies and pattern validation rules."""

    def __init__(self, root_dir: Path | None = None):
        self.config = get_config()
        self.root = root_dir or self.config.root
        self.manifest_path = self.root / "ami/config/policies/manifest.yaml"
        self._manifest = self._load_manifest()
        # Instance-level caches to avoid lru_cache on methods
        self._bash_cache: list[BashCacheEntry] = []
        self._python_cache: list[PythonPattern] | None = None
        self._sensitive_cache: list[BashPattern] | None = None
        self._communication_cache: list[BashPattern] | None = None
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
        if not isinstance(self._manifest, dict):
            return None
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

        # If we exhausted keys and ended with a string, return path; else None
        return self.root / current if isinstance(current, str) else None

    def _get_cached_bash(self, name: str) -> list[BashPattern] | None:
        """Look up cached bash patterns by name."""
        for entry in self._bash_cache:
            if entry.name == name:
                return entry.patterns
        return None

    def load_bash_patterns(self, name: str = "default") -> list[BashPattern]:
        """Load Bash command validation patterns."""
        cached = self._get_cached_bash(name)
        if cached is not None:
            return cached

        path = self._get_policy_path("bash", name)
        if not path or not path.exists():
            self._bash_cache.append(BashCacheEntry(name, []))
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns = data.get("deny_patterns", []) if isinstance(data, dict) else []
        self._bash_cache.append(BashCacheEntry(name, patterns))
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
        patterns = data.get("patterns", []) if isinstance(data, dict) else []
        self._python_cache = patterns
        return patterns

    def load_sensitive_patterns(self) -> list[BashPattern]:
        """Load sensitive file patterns."""
        if self._sensitive_cache is not None:
            return self._sensitive_cache

        path = self._get_policy_path("sensitive", "files")
        if not path or not path.exists():
            self._sensitive_cache = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns = data.get("sensitive_patterns", []) if isinstance(data, dict) else []
        self._sensitive_cache = patterns
        return patterns

    def load_communication_patterns(self) -> list[BashPattern]:
        """Load prohibited communication patterns."""
        if self._communication_cache is not None:
            return self._communication_cache

        path = self._get_policy_path("communication", "prohibited")
        if not path or not path.exists():
            self._communication_cache = []
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        patterns = data.get("prohibited_patterns", []) if isinstance(data, dict) else []
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
_singleton = {}


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance."""
    if "engine" not in _singleton:
        _singleton["engine"] = PolicyEngine()
    return _singleton["engine"]

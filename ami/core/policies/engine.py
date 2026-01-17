"""Unified Policy Engine for AMI Agent security and quality guards.

Centralizes the loading and management of YAML-based policies and patterns.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

import yaml

from ami.core.config import get_config


class PolicyEngine:
    """Manages system-wide policies and pattern validation rules."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.config = get_config()
        self.root = root_dir or self.config.root
        self.manifest_path = self.root / "ami/config/policies/manifest.yaml"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        """Load the policy manifest."""
        if not self.manifest_path.exists():
            return {}
        with self.manifest_path.open() as f:
            return yaml.safe_load(f)

    def _get_policy_path(self, *keys: str) -> Optional[Path]:
        """Get policy path from manifest using dot-notation keys."""
        data = self._manifest.get("policies", {})
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return None
        return self.root / data if data else None

    @lru_cache(maxsize=16)
    def load_bash_patterns(self, name: str = "default") -> List[Dict[str, str]]:
        """Load Bash command validation patterns."""
        path = self._get_policy_path("bash", name)
        if not path or not path.exists():
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        return data.get("deny_patterns", [])

    @lru_cache(maxsize=4)
    def load_python_patterns(self) -> List[Dict[str, Any]]:
        """Load Python fast pattern validation rules."""
        path = self._get_policy_path("python", "fast")
        if not path or not path.exists():
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        return data.get("patterns", [])

    @lru_cache(maxsize=4)
    def load_sensitive_patterns(self) -> List[Dict[str, str]]:
        """Load sensitive file patterns."""
        path = self._get_policy_path("sensitive", "files")
        if not path or not path.exists():
            return []

        with path.open() as f:
            data = yaml.safe_load(f)
        return data.get("sensitive_patterns", [])

    @lru_cache(maxsize=1)
    def load_exemptions(self) -> Set[str]:
        """Load file exemptions for pattern checks."""
        path = self._get_policy_path("exemptions", "files")
        if not path or not path.exists():
            return set()

        with path.open() as f:
            data = yaml.safe_load(f)
        return set(data.get("pattern_check_exemptions", []))


# Global singleton instance
_engine: Optional[PolicyEngine] = None

def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance."""
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine

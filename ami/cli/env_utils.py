"""Utilities for environment and privilege management.

This module contains environment and privilege-related utilities extracted from utils.py
to reduce code size and improve maintainability.
"""

import os
import pwd
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from ami.types.common import ProcessEnvironment

if TYPE_CHECKING:
    from ami.core.config import ConfigValue


class ConfigProtocol(Protocol):
    """Protocol for configuration objects with get_value method."""

    def get_value(
        self,
        key: str,
        default: "ConfigValue" = None,
    ) -> "ConfigValue":
        """Get configuration value by key."""
        ...


def drop_privileges(config: ConfigProtocol) -> None:
    """Drop privileges to the unprivileged user specified in config.

    Args:
        config: Configuration object containing unprivileged_user setting
    """

    def _verify_privilege_drop(expected_uid: int, expected_gid: int) -> None:
        """Verify that privileges were successfully dropped."""
        if os.getuid() != expected_uid or os.getgid() != expected_gid:
            msg = "privilege drop failed"
            raise RuntimeError(msg)

    unprivileged_user_value = config.get_value("unprivileged_user")
    unprivileged_user = (
        str(unprivileged_user_value) if unprivileged_user_value else None
    )
    if not unprivileged_user:
        return

    try:
        user_info = pwd.getpwnam(unprivileged_user)
        uid = user_info.pw_uid
        gid = user_info.pw_gid

        os.setgid(gid)
        os.setuid(uid)

        _verify_privilege_drop(uid, gid)
    except Exception as e:
        logger.error(f"Failed to drop privileges: {e}")


def get_unprivileged_env(config: ConfigProtocol) -> ProcessEnvironment | None:
    """Get environment to run subprocess with unprivileged user.

    Args:
        config: Configuration object containing unprivileged_user setting

    Returns:
        ProcessEnvironment with HOME and USER set to unprivileged user,
        or None if unprivileged user is not configured
    """
    unprivileged_user_value = config.get_value("unprivileged_user")
    unprivileged_user = (
        str(unprivileged_user_value) if unprivileged_user_value else None
    )
    if not unprivileged_user:
        return None

    try:
        user_info = pwd.getpwnam(unprivileged_user)
        env = ProcessEnvironment(
            HOME=user_info.pw_dir,
            USER=unprivileged_user,
            PATH=os.environ.get("PATH", ""),
            LANG=os.environ.get("LANG", "C.UTF-8"),
            LC_ALL=os.environ.get("LC_ALL", "C.UTF-8"),
            PYTHONUNBUFFERED="1",
            FORCE_COLOR="1",
        )

        if "DISABLE_AUTOUPDATER" in os.environ:
            env["DISABLE_AUTOUPDATER"] = os.environ["DISABLE_AUTOUPDATER"]
    except KeyError:
        logger.warning(
            f"Unprivileged user '{unprivileged_user}' not found. "
            "Running as current user."
        )
        env = ProcessEnvironment(
            HOME=os.environ.get("HOME", ""),
            USER=os.environ.get("USER", ""),
            PATH=os.environ.get("PATH", ""),
            LANG=os.environ.get("LANG", "C.UTF-8"),
            LC_ALL=os.environ.get("LC_ALL", "C.UTF-8"),
            PYTHONUNBUFFERED="1",
            FORCE_COLOR="1",
        )
        return env
    else:
        return env

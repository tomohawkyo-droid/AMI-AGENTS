"""Integration tests for docker stats and systemd status modules
with mocked run_cmd (part 2).

Exercises: ami/cli_components/status_containers.py,
ami/cli_components/status_systemd.py
All subprocess calls are mocked via unittest.mock.patch on run_cmd.
"""

from unittest.mock import patch

import pytest

from ami.cli_components.status_containers import get_system_docker_stats
from ami.cli_components.status_systemd import (
    _extract_compose_info,
    _parse_systemd_details,
    _process_service,
)
from ami.core.config import _ConfigSingleton
from ami.types.status import PodmanContainer, SystemdService

CONT_PATCH = "ami.cli_components.status_containers.run_cmd"
CONT_EXISTS = "ami.cli_components.status_containers.os.path.exists"
SYS_PORTS = "ami.cli_components.status_systemd.get_local_ports"

# ---------------------------------------------------------------------------
# Constants for magic number comparisons
# ---------------------------------------------------------------------------
EXPECTED_PAIR_COUNT = 2
EXPECTED_SUDO_CALL_COUNT = 2
EXPECTED_CHILD_ITEMS_COUNT = 2


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _container(name, **kw):
    defaults = {
        "id": "abcdef123456",
        "name": name,
        "state": "running",
        "image": "img:v1.0",
    }
    defaults.update(kw)
    return PodmanContainer(**defaults)


# ---------------------------------------------------------------------------
# 8. get_system_docker_stats
# ---------------------------------------------------------------------------


def _find_docker_stat_by_name(stats, name):
    """Helper to find a docker stat entry by name."""
    for s in stats:
        if s["name"] == name:
            return s
    return None


class TestGetSystemDockerStats:
    def test_not_installed(self):
        with patch(CONT_EXISTS, return_value=False):
            assert get_system_docker_stats() == []

    def test_pipe_separated(self):
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_PATCH, return_value="ng|2.5%|128M\nrd|0.3%|64M"),
        ):
            s = get_system_docker_stats()
        stat_ng = _find_docker_stat_by_name(s, "ng")
        stat_rd = _find_docker_stat_by_name(s, "rd")
        assert stat_ng is not None
        assert stat_ng["cpu"] == "2.5%"
        assert stat_ng["mem_usage"] == "128M"
        assert stat_rd["cpu"] == "0.3%"

    def test_empty(self):
        with patch(CONT_EXISTS, return_value=True), patch(CONT_PATCH, return_value=""):
            assert get_system_docker_stats() == []

    def test_skips_few_parts(self):
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_PATCH, return_value="bad|cpu\ngood|1%|100M"),
        ):
            s = get_system_docker_stats()
        assert _find_docker_stat_by_name(s, "bad") is None
        assert _find_docker_stat_by_name(s, "good") is not None

    def test_sudo_fallback(self):
        calls = []

        def cmd(c):
            calls.append(c)
            return "a|5%|256M" if "sudo" in c else ""

        with patch(CONT_EXISTS, return_value=True), patch(CONT_PATCH, side_effect=cmd):
            s = get_system_docker_stats()
        assert _find_docker_stat_by_name(s, "a") is not None
        assert len(calls) == EXPECTED_SUDO_CALL_COUNT


# ---------------------------------------------------------------------------
# 9. _parse_systemd_details
# ---------------------------------------------------------------------------


class TestParseSystemdDetails:
    def test_standard(self):
        raw = "Id=svc.service\nActiveState=active\nSubState=running\nMainPID=123"
        r = _parse_systemd_details(raw)
        assert r["Id"] == "svc.service"
        assert r["MainPID"] == "123"

    def test_value_with_equals(self):
        r = _parse_systemd_details("ExecStart=/bin/foo arg=val")
        assert r["ExecStart"] == "/bin/foo arg=val"

    def test_empty(self):
        result = _parse_systemd_details("")
        # Empty input returns a TypedDict with empty values
        assert result["Id"] == ""
        assert result["ActiveState"] == ""

    def test_no_equals_skipped(self):
        r = _parse_systemd_details("Id=x\ngarbage\nActiveState=b")
        # Lines without equals are skipped
        assert r["Id"] == "x"
        assert r["ActiveState"] == "b"
        # Garbage line without = should not affect results

    def test_empty_value(self):
        r = _parse_systemd_details("ExecStart=\nRestart=no")
        assert r["ExecStart"] == ""
        assert r["Restart"] == "no"


# ---------------------------------------------------------------------------
# 10. _extract_compose_info
# ---------------------------------------------------------------------------


class TestExtractComposeInfo:
    def test_podman_start(self):
        c, f, p = _extract_compose_info("/usr/bin/podman start -a my-ctr")
        assert c == "my-ctr"
        assert f is None
        assert p == []

    def test_compose_file_and_profiles(self):
        _c, f, p = _extract_compose_info(
            "/usr/bin/podman-compose -f dc.yml --profile web --profile api up"
        )
        assert f == "dc.yml"
        assert p == ["web", "api"]

    def test_compose_no_profiles(self):
        _, f, p = _extract_compose_info("/usr/bin/podman-compose -f stack.yml up")
        assert f == "stack.yml"
        assert p == []

    def test_unrelated_command(self):
        c, f, p = _extract_compose_info("/usr/bin/python3 app.py")
        assert c is None
        assert f is None
        assert p == []

    def test_start_and_compose_combined(self):
        c, f, _p = _extract_compose_info(
            "/usr/bin/podman start -a web && podman-compose -f a.yml up"
        )
        assert c == "web"
        assert f == "a.yml"


# ---------------------------------------------------------------------------
# 11. _process_service
# ---------------------------------------------------------------------------


class TestProcessService:
    def test_compose_unified_stack(self):
        svc = SystemdService(
            name="ami-compose.service",
            compose_file="dc.yml",
            compose_profiles=["web", "api"],
        )
        containers = [
            _container(
                "w", labels={"com.docker.compose.project.config_files": "/p/dc.yml"}
            ),
            _container(
                "a", labels={"com.docker.compose.project.config_files": "/p/dc.yml"}
            ),
            _container(
                "x", labels={"com.docker.compose.project.config_files": "other.yml"}
            ),
        ]
        processed: set[str] = set()
        info = _process_service(svc, containers, processed)
        assert info.row_type == "Unified Stack"
        assert {"w", "a"} == processed
        assert len(info.child_items) == EXPECTED_CHILD_ITEMS_COUNT
        assert "Profiles: web, api" in info.row_details

    def test_compose_default_profile(self):
        svc = SystemdService(name="s", compose_file="dc.yml", compose_profiles=[])
        info = _process_service(svc, [], set())
        assert "Profiles: default" in info.row_details

    def test_container_wrapper(self):
        svc = SystemdService(name="ami-redis.service", managed_container="redis")
        processed: set[str] = set()
        info = _process_service(svc, [_container("redis")], processed)
        assert info.row_type == "Container Wrapper"
        assert "redis" in processed
        assert len(info.child_items) == 1

    def test_container_wrapper_missing(self):
        svc = SystemdService(name="s", managed_container="gone")
        info = _process_service(svc, [], set())
        assert info.row_type == "Container Wrapper"
        assert info.child_items == []

    def test_local_process_with_ports(self):
        svc = SystemdService(name="s", pid="5678")
        with patch(SYS_PORTS, return_value=["8080", "9090"]):
            info = _process_service(svc, [], set())
        assert info.row_type == "Local Process"
        assert info.ports_str == "8080, 9090"

    def test_local_process_no_ports(self):
        svc = SystemdService(name="s", pid="5678")
        with patch(SYS_PORTS, return_value=[]):
            info = _process_service(svc, [], set())
        assert info.ports_str == ""

    def test_local_process_pid_zero(self):
        svc = SystemdService(name="s", pid="0")
        info = _process_service(svc, [], set())
        assert info.row_type == "Local Process"
        assert info.ports_str == ""

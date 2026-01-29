"""Integration tests for container status modules with mocked run_cmd (part 3).

Exercises: ami/cli_components/status_containers.py - get_system_docker_containers
All subprocess calls are mocked via unittest.mock.patch on run_cmd.
"""

import json
from unittest.mock import patch

import pytest

from ami.cli_components.status_containers import get_system_docker_containers
from ami.core.config import _ConfigSingleton

CONT_PATCH = "ami.cli_components.status_containers.run_cmd"
CONT_EXISTS = "ami.cli_components.status_containers.os.path.exists"

# ---------------------------------------------------------------------------
# Constants for magic number comparisons
# ---------------------------------------------------------------------------
EXPECTED_PROXY_PORT_COUNT = 2
EXPECTED_PROXY_HOST_PORT = 8080
EXPECTED_PROXY_CONTAINER_PORT = 443
EXPECTED_SUDO_CALL_COUNT = 2
EXPECTED_MULTI_CONTAINER_COUNT = 2


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _find_container_by_name(containers, name):
    """Helper to find a container by name in a list."""
    for c in containers:
        if c.name == name:
            return c
    return None


# ---------------------------------------------------------------------------
# get_system_docker_containers
# ---------------------------------------------------------------------------


class TestGetSystemDockerContainers:
    def test_not_installed(self):
        with patch(CONT_EXISTS, return_value=False):
            assert get_system_docker_containers() == []

    def test_parses_port_string(self):
        line = json.dumps(
            {
                "ID": "aabbcc",
                "Names": "proxy",
                "State": "running",
                "Status": "Up",
                "Image": "nginx",
                "Ports": "0.0.0.0:8080->80/tcp, 0.0.0.0:8443->443/tcp",
            }
        )
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_PATCH, return_value=line),
        ):
            c = get_system_docker_containers()
        container = _find_container_by_name(c, "proxy")
        assert container is not None
        assert len(container.ports) == EXPECTED_PROXY_PORT_COUNT
        assert container.ports[0].host_port == EXPECTED_PROXY_HOST_PORT
        assert container.ports[1].container_port == EXPECTED_PROXY_CONTAINER_PORT

    def test_no_ports(self):
        line = json.dumps(
            {
                "ID": "ff1122",
                "Names": "wrk",
                "State": "running",
                "Status": "Up",
                "Image": "w",
                "Ports": "",
            }
        )
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_PATCH, return_value=line),
        ):
            containers = get_system_docker_containers()
            container = _find_container_by_name(containers, "wrk")
            assert container is not None
            assert container.ports == []

    def test_sudo_fallback(self):
        line = json.dumps(
            {
                "ID": "001122",
                "Names": "sec",
                "State": "running",
                "Status": "Up",
                "Image": "v",
                "Ports": "",
            }
        )
        calls = []

        def cmd(c):
            calls.append(c)
            return line if "sudo" in c else ""

        with patch(CONT_EXISTS, return_value=True), patch(CONT_PATCH, side_effect=cmd):
            containers = get_system_docker_containers()
            assert _find_container_by_name(containers, "sec") is not None
        assert len(calls) == EXPECTED_SUDO_CALL_COUNT

    def test_empty_output(self):
        with patch(CONT_EXISTS, return_value=True), patch(CONT_PATCH, return_value=""):
            assert get_system_docker_containers() == []

    def test_multiple_lines(self):
        lines = "\n".join(
            [
                json.dumps(
                    {
                        "ID": "a",
                        "Names": "c1",
                        "State": "r",
                        "Status": "U",
                        "Image": "i",
                        "Ports": "",
                    }
                ),
                json.dumps(
                    {
                        "ID": "b",
                        "Names": "c2",
                        "State": "r",
                        "Status": "U",
                        "Image": "i",
                        "Ports": "",
                    }
                ),
            ]
        )
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_PATCH, return_value=lines),
        ):
            assert len(get_system_docker_containers()) == EXPECTED_MULTI_CONTAINER_COUNT

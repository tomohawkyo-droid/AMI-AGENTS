"""Integration tests for container status modules with mocked run_cmd (part 1).

Exercises: ami/cli_components/status_containers.py
All subprocess calls are mocked via unittest.mock.patch on run_cmd.
"""

import json
from unittest.mock import patch

import pytest

from ami.cli_components.status_containers import (
    _get_container_inspect_info,
    _parse_port_mapping,
    get_container_sizes,
    get_container_stats,
    get_container_volumes,
    get_podman_containers,
    get_system_docker_containers,
)
from ami.core.config import _ConfigSingleton

CONT_PATCH = "ami.cli_components.status_containers.run_cmd"
CONT_EXISTS = "ami.cli_components.status_containers.os.path.exists"

# ---------------------------------------------------------------------------
# Constants for magic number comparisons
# ---------------------------------------------------------------------------
EXPECTED_PORT_COUNT = 2
EXPECTED_HTTP_PORT = 80
EXPECTED_HTTPS_PORT = 443
EXPECTED_CONTAINER_SIZE_COUNT = 3
EXPECTED_VOLUME_COUNT = 2
EXPECTED_PROXY_PORT_COUNT = 2
EXPECTED_PROXY_HOST_PORT = 8080
EXPECTED_PROXY_CONTAINER_PORT = 443
EXPECTED_DB_PORT = 5432
EXPECTED_SUDO_CALL_COUNT = 2
EXPECTED_MULTI_CONTAINER_COUNT = 2


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# 1. _parse_port_mapping
# ---------------------------------------------------------------------------


class TestParsePortMapping:
    def test_camel_case(self):
        pm = _parse_port_mapping(
            {"hostPort": 9090, "containerPort": 80, "protocol": "tcp"}
        )
        assert (pm.host_port, pm.container_port, pm.protocol) == (9090, 80, "tcp")

    def test_pascal_case(self):
        pm = _parse_port_mapping(
            {"HostPort": "3000", "ContainerPort": "3000", "Protocol": "udp"}
        )
        assert (pm.host_port, pm.container_port, pm.protocol) == (3000, 3000, "udp")

    def test_snake_case(self):
        pm = _parse_port_mapping({"host_port": 443, "container_port": 8443})
        assert (pm.host_port, pm.container_port, pm.protocol) == (443, 8443, "tcp")

    def test_default_protocol(self):
        assert _parse_port_mapping({"hostPort": 1}).protocol == "tcp"

    def test_empty_dict(self):
        pm = _parse_port_mapping({})
        assert pm.host_port is None
        assert pm.container_port is None

    def test_string_values_cast(self):
        pm = _parse_port_mapping({"hostPort": "8080", "containerPort": "80"})
        assert (pm.host_port, pm.container_port) == (8080, 80)


# ---------------------------------------------------------------------------
# 2. _get_container_inspect_info
# ---------------------------------------------------------------------------


class TestGetContainerInspectInfo:
    def test_returns_ports_and_labels(self):
        data = json.dumps(
            [
                {
                    "Config": {
                        "ExposedPorts": {"80/tcp": {}, "443/tcp": {}},
                        "Labels": {"app": "web"},
                    }
                }
            ]
        )
        with patch(CONT_PATCH, return_value=data):
            ports, labels = _get_container_inspect_info("c", "podman")
        assert len(ports) == EXPECTED_PORT_COUNT
        assert ports[0].container_port == EXPECTED_HTTP_PORT
        assert ports[1].container_port == EXPECTED_HTTPS_PORT
        assert labels["app"] == "web"

    def test_empty_output(self):
        with patch(CONT_PATCH, return_value=""):
            assert _get_container_inspect_info("c", "podman") == ([], {})

    def test_invalid_json(self):
        with patch(CONT_PATCH, return_value="{bad"):
            assert _get_container_inspect_info("c", "podman") == ([], {})

    def test_empty_array(self):
        with patch(CONT_PATCH, return_value="[]"):
            assert _get_container_inspect_info("c", "podman") == ([], {})

    def test_null_labels(self):
        with patch(CONT_PATCH, return_value=json.dumps([{"Config": {"Labels": None}}])):
            _, labels = _get_container_inspect_info("c", "podman")
        assert labels == {}


# ---------------------------------------------------------------------------
# 3. get_container_stats
# ---------------------------------------------------------------------------


class TestGetContainerStats:
    def test_standard_keys(self):
        d = json.dumps(
            [{"Name": "w", "CPU": "5%", "MemUsage": "100M", "MemPerc": "10%"}]
        )
        with patch(CONT_PATCH, return_value=d):
            s = get_container_stats()
        assert s["w"] == {"cpu": "5%", "mem_usage": "100M", "mem_percent": "10%"}

    def test_alternate_keys(self):
        d = json.dumps(
            [
                {
                    "name": "a",
                    "cpu_percent": "3%",
                    "mem_usage": "64M",
                    "mem_percent": "2%",
                }
            ]
        )
        with patch(CONT_PATCH, return_value=d):
            assert get_container_stats()["a"]["cpu"] == "3%"

    def test_empty(self):
        with patch(CONT_PATCH, return_value=""):
            assert get_container_stats() == {}

    def test_invalid_json(self):
        with patch(CONT_PATCH, return_value="nope"):
            assert get_container_stats() == {}

    def test_skips_no_name(self):
        d = json.dumps([{"CPU": "1%"}, {"Name": "v", "CPU": "2%"}])
        with patch(CONT_PATCH, return_value=d):
            s = get_container_stats()
        assert len(s) == 1
        assert "v" in s


# ---------------------------------------------------------------------------
# 4. get_container_sizes
# ---------------------------------------------------------------------------


class TestGetContainerSizes:
    def test_virtual_format(self):
        with patch(CONT_PATCH, return_value="web\t22kB (virtual 198MB)"):
            s = get_container_sizes()
        assert s["web"] == {"writable": "22kB", "virtual": "198MB"}

    def test_no_parens(self):
        with patch(CONT_PATCH, return_value="app\t50kB"):
            s = get_container_sizes()
        assert s["app"] == {"writable": "50kB", "virtual": "-"}

    def test_empty(self):
        with patch(CONT_PATCH, return_value=""):
            assert get_container_sizes() == {}

    def test_skips_no_tab(self):
        with patch(CONT_PATCH, return_value="notab\nok\t10kB"):
            s = get_container_sizes()
        assert "notab" not in s
        assert "ok" in s

    def test_multiple(self):
        with patch(
            CONT_PATCH, return_value="a\t1 (virtual 10)\nb\t2 (virtual 20)\nc\t3"
        ):
            assert len(get_container_sizes()) == EXPECTED_CONTAINER_SIZE_COUNT


# ---------------------------------------------------------------------------
# 5. get_container_volumes
# ---------------------------------------------------------------------------


class TestGetContainerVolumes:
    def _inspect(self, mounts):
        return json.dumps([{"Mounts": mounts}])

    def test_large_volume_returned(self):
        insp = self._inspect(
            [{"Source": "/data", "Destination": "/app", "Type": "bind"}]
        )

        def cmd(c):
            return insp if "inspect" in c else "1048576"

        with patch(CONT_PATCH, side_effect=cmd):
            v = get_container_volumes("x")
        assert len(v) == 1
        assert v[0]["dst"] == "/app"

    def test_small_volume_skipped(self):
        insp = self._inspect([{"Source": "/t", "Destination": "/m", "Type": "bind"}])

        def cmd(c):
            return insp if "inspect" in c else "100"

        with patch(CONT_PATCH, side_effect=cmd):
            assert get_container_volumes("x") == []

    def test_empty_inspect(self):
        with patch(CONT_PATCH, return_value=""):
            assert get_container_volumes("x") == []

    def test_invalid_json(self):
        with patch(CONT_PATCH, return_value="bad"):
            assert get_container_volumes("x") == []

    def test_non_numeric_du(self):
        insp = self._inspect([{"Source": "/s", "Destination": "/d", "Type": "bind"}])

        def cmd(c):
            return insp if "inspect" in c else "error"

        with patch(CONT_PATCH, side_effect=cmd):
            assert get_container_volumes("x") == []

    def test_skips_no_destination(self):
        insp = self._inspect([{"Source": "/s", "Type": "bind"}])

        def cmd(c):
            return insp if "inspect" in c else "999999"

        with patch(CONT_PATCH, side_effect=cmd):
            assert get_container_volumes("x") == []

    def test_mixed_sizes(self):
        insp = self._inspect(
            [
                {"Source": "/big", "Destination": "/m1", "Type": "volume"},
                {"Source": "/small", "Destination": "/m2", "Type": "bind"},
                {"Source": "/big2", "Destination": "/m3", "Type": "bind"},
            ]
        )
        sizes = {"/big": "500000", "/small": "10", "/big2": "65536"}

        def cmd(c):
            if "inspect" in c:
                return insp
            for p, s in sizes.items():
                if p in c:
                    return s
            return "0"

        with patch(CONT_PATCH, side_effect=cmd):
            v = get_container_volumes("x")
        assert len(v) == EXPECTED_VOLUME_COUNT
        assert {x["dst"] for x in v} == {"/m1", "/m3"}

    def test_alternate_key_names(self):
        insp = self._inspect([{"source": "/a", "destination": "/b", "type": "bind"}])

        def cmd(c):
            return insp if "inspect" in c else "100000"

        with patch(CONT_PATCH, side_effect=cmd):
            v = get_container_volumes("x")
        assert len(v) == 1
        assert v[0]["src"] == "/a"


# ---------------------------------------------------------------------------
# 6. get_podman_containers
# ---------------------------------------------------------------------------


class TestGetPodmanContainers:
    def test_with_ports_and_labels(self):
        ps = json.dumps(
            [
                {
                    "Id": "abc123def456",
                    "Names": ["web"],
                    "State": "running",
                    "Status": "Up",
                    "Image": "nginx",
                    "Ports": [{"hostPort": 80, "containerPort": 80, "protocol": "tcp"}],
                }
            ]
        )
        insp = json.dumps([{"Config": {"ExposedPorts": {}, "Labels": {"k": "v"}}}])

        def cmd(c):
            return ps if "ps -a" in c else insp

        with patch(CONT_PATCH, side_effect=cmd):
            ct = get_podman_containers()
        assert ct["web"].ports[0].host_port == EXPECTED_HTTP_PORT
        assert ct["web"].labels["k"] == "v"

    def test_falls_back_to_exposed(self):
        ps = json.dumps(
            [
                {
                    "Id": "xyz000000000",
                    "Names": ["db"],
                    "State": "running",
                    "Status": "Up",
                    "Image": "pg",
                    "Ports": [],
                }
            ]
        )
        insp = json.dumps(
            [{"Config": {"ExposedPorts": {"5432/tcp": {}}, "Labels": {}}}]
        )

        def cmd(c):
            return ps if "ps -a" in c else insp

        with patch(CONT_PATCH, side_effect=cmd):
            assert (
                get_podman_containers()["db"].ports[0].container_port
                == EXPECTED_DB_PORT
            )

    def test_empty(self):
        with patch(CONT_PATCH, return_value=""):
            assert get_podman_containers() == {}

    def test_invalid_json(self):
        with patch(CONT_PATCH, return_value="bad"):
            assert get_podman_containers() == {}

    def test_no_names_uses_id(self):
        ps = json.dumps(
            [
                {
                    "Id": "abcdef123456789",
                    "Names": [],
                    "State": "exited",
                    "Status": "Exited",
                    "Image": "alp",
                }
            ]
        )
        insp = json.dumps([{"Config": {"Labels": {}}}])

        def cmd(c):
            return ps if "ps -a" in c else insp

        with patch(CONT_PATCH, side_effect=cmd):
            assert "abcdef123456" in get_podman_containers()


# ---------------------------------------------------------------------------
# 7. get_system_docker_containers
# ---------------------------------------------------------------------------


class TestGetSystemDockerContainers:
    def test_not_installed(self):
        with patch(CONT_EXISTS, return_value=False):
            assert get_system_docker_containers() == {}

    def test_parses_port_string(self):
        line = json.dumps(
            {
                "ID": "aabbcc",
                "Names": "proxy",
                "State": "running",
                "Status": "Up",
                "Image": "nginx",
                "Ports": "0.0.0.0:8080->80/tcp, 0.0.0.0:443->443/tcp",
            }
        )
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_PATCH, return_value=line),
        ):
            c = get_system_docker_containers()
        assert len(c["proxy"].ports) == EXPECTED_PROXY_PORT_COUNT
        assert c["proxy"].ports[0].host_port == EXPECTED_PROXY_HOST_PORT
        assert c["proxy"].ports[1].container_port == EXPECTED_PROXY_CONTAINER_PORT

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
            assert get_system_docker_containers()["wrk"].ports == []

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
            assert "sec" in get_system_docker_containers()
        assert len(calls) == EXPECTED_SUDO_CALL_COUNT

    def test_empty_output(self):
        with patch(CONT_EXISTS, return_value=True), patch(CONT_PATCH, return_value=""):
            assert get_system_docker_containers() == {}

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

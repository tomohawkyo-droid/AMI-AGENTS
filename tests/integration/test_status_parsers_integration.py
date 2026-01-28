"""Integration tests for status parsing and display utilities.

Exercises: cli_components/status_containers.py, cli_components/status_systemd.py,
cli_components/status_utils.py (remaining functions)
"""

import json
from unittest.mock import patch

import pytest

from ami.cli_components.status_containers import (
    _parse_port_mapping,
    get_container_sizes,
    get_container_stats,
)
from ami.cli_components.status_systemd import (
    _extract_compose_info,
    _parse_systemd_details,
    _process_service,
)
from ami.cli_components.status_utils import (
    _format_port_string,
    _get_container_status_display,
    _get_restart_icon,
    parse_size_to_bytes,
    print_box_line,
    run_cmd,
)
from ami.core.config import _ConfigSingleton
from ami.types.status import PodmanContainer, PortMapping, SystemdService

# ---------------------------------------------------------------------------
# Named constants for magic values used in assertions
# ---------------------------------------------------------------------------
EXPECTED_HOST_PORT_STANDARD = 8080
EXPECTED_CONTAINER_PORT_STANDARD = 80
EXPECTED_PORT_ALTERNATE = 3000
EXPECTED_PORT_HTTPS = 443
EXPECTED_BYTES_1024 = 1024
EXPECTED_CHILD_ITEMS_COUNT = 1


@pytest.fixture(autouse=True)
def _ensure_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


# ---------------------------------------------------------------------------
# Port mapping parsing
# ---------------------------------------------------------------------------


class TestParsePortMapping:
    """Test _parse_port_mapping from status_containers."""

    def test_standard_keys(self):
        pm = _parse_port_mapping(
            {"hostPort": 8080, "containerPort": 80, "protocol": "tcp"}
        )
        assert pm.host_port == EXPECTED_HOST_PORT_STANDARD
        assert pm.container_port == EXPECTED_CONTAINER_PORT_STANDARD
        assert pm.protocol == "tcp"

    def test_alternate_keys(self):
        pm = _parse_port_mapping(
            {"HostPort": "3000", "ContainerPort": "3000", "Protocol": "udp"}
        )
        assert pm.host_port == EXPECTED_PORT_ALTERNATE
        assert pm.container_port == EXPECTED_PORT_ALTERNATE
        assert pm.protocol == "udp"

    def test_snake_case_keys(self):
        pm = _parse_port_mapping({"host_port": 443, "container_port": 443})
        assert pm.host_port == EXPECTED_PORT_HTTPS
        assert pm.protocol == "tcp"  # default

    def test_missing_ports(self):
        pm = _parse_port_mapping({})
        assert pm.host_port is None
        assert pm.container_port is None


# ---------------------------------------------------------------------------
# Container stats parsing
# ---------------------------------------------------------------------------


class TestGetContainerStats:
    """Test get_container_stats with mocked run_cmd."""

    def test_parses_stats_json(self):
        mock_data = json.dumps(
            [
                {"Name": "web", "CPU": "5%", "MemUsage": "100MB", "MemPerc": "10%"},
                {"Name": "db", "CPU": "2%", "MemUsage": "500MB", "MemPerc": "50%"},
            ]
        )
        with patch(
            "ami.cli_components.status_containers.run_cmd", return_value=mock_data
        ):
            stats = get_container_stats()
        assert "web" in stats
        assert stats["web"]["cpu"] == "5%"
        assert "db" in stats
        assert stats["db"]["mem_usage"] == "500MB"

    def test_empty_output(self):
        with patch("ami.cli_components.status_containers.run_cmd", return_value=""):
            stats = get_container_stats()
        assert stats == {}

    def test_invalid_json(self):
        with patch(
            "ami.cli_components.status_containers.run_cmd", return_value="not json"
        ):
            stats = get_container_stats()
        assert stats == {}

    def test_alt_key_names(self):
        mock_data = json.dumps(
            [
                {
                    "name": "alt",
                    "cpu_percent": "3%",
                    "mem_usage": "200MB",
                    "mem_percent": "20%",
                },
            ]
        )
        with patch(
            "ami.cli_components.status_containers.run_cmd", return_value=mock_data
        ):
            stats = get_container_stats()
        assert "alt" in stats
        assert stats["alt"]["cpu"] == "3%"


# ---------------------------------------------------------------------------
# Container sizes parsing
# ---------------------------------------------------------------------------


class TestGetContainerSizes:
    """Test get_container_sizes with mocked run_cmd."""

    def test_parses_sizes(self):
        raw = "web\t22kB (virtual 198MB)\ndb\t100kB (virtual 500MB)"
        with patch("ami.cli_components.status_containers.run_cmd", return_value=raw):
            sizes = get_container_sizes()
        assert "web" in sizes
        assert sizes["web"]["writable"] == "22kB"
        assert sizes["web"]["virtual"] == "198MB"

    def test_no_virtual(self):
        raw = "app\t50kB"
        with patch("ami.cli_components.status_containers.run_cmd", return_value=raw):
            sizes = get_container_sizes()
        assert sizes["app"]["writable"] == "50kB"

    def test_empty_output(self):
        with patch("ami.cli_components.status_containers.run_cmd", return_value=""):
            sizes = get_container_sizes()
        assert sizes == {}


# ---------------------------------------------------------------------------
# Systemd detail parsing
# ---------------------------------------------------------------------------


class TestParseSystemdDetails:
    """Test _parse_systemd_details."""

    def test_basic_parsing(self):
        raw = "Id=test.service\nActiveState=active\nSubState=running"
        result = _parse_systemd_details(raw)
        assert result["Id"] == "test.service"
        assert result["ActiveState"] == "active"
        assert result["SubState"] == "running"

    def test_value_with_equals(self):
        raw = "ExecStart=/usr/bin/python3 arg1=val1"
        result = _parse_systemd_details(raw)
        assert result["ExecStart"] == "/usr/bin/python3 arg1=val1"

    def test_empty_input(self):
        result = _parse_systemd_details("")
        assert result == {}


# ---------------------------------------------------------------------------
# Compose info extraction
# ---------------------------------------------------------------------------


class TestExtractComposeInfo:
    """Test _extract_compose_info."""

    def test_podman_start(self):
        exec_start = "/usr/bin/podman start -a mycontainer"
        container, compose_file, profiles = _extract_compose_info(exec_start)
        assert container == "mycontainer"
        assert compose_file is None
        assert profiles == []

    def test_podman_compose(self):
        exec_start = (
            "/usr/bin/podman-compose -f docker-compose.yml "
            "--profile web --profile api up -d"
        )
        _container, compose_file, profiles = _extract_compose_info(exec_start)
        assert compose_file == "docker-compose.yml"
        assert "web" in profiles
        assert "api" in profiles

    def test_no_match(self):
        exec_start = "/usr/bin/python3 app.py"
        container, compose_file, profiles = _extract_compose_info(exec_start)
        assert container is None
        assert compose_file is None
        assert profiles == []


# ---------------------------------------------------------------------------
# _process_service
# ---------------------------------------------------------------------------


class TestProcessService:
    """Test _process_service with various service types."""

    def _make_container(self, name: str, **kwargs) -> PodmanContainer:
        return PodmanContainer(id="abc", name=name, state="running", **kwargs)

    def test_compose_service(self):
        svc = SystemdService(
            name="ami-compose.service",
            compose_file="docker-compose.yml",
            compose_profiles=["web"],
        )
        containers = {
            "web": self._make_container(
                "web",
                labels={
                    "com.docker.compose.project.config_files": "docker-compose.yml"
                },
            )
        }
        processed: set[str] = set()
        info = _process_service(svc, containers, processed)
        assert info.row_type == "Unified Stack"
        assert "web" in processed
        assert len(info.child_items) == EXPECTED_CHILD_ITEMS_COUNT

    def test_container_wrapper(self):
        svc = SystemdService(
            name="ami-myapp.service",
            managed_container="myapp",
        )
        containers = {"myapp": self._make_container("myapp")}
        processed: set[str] = set()
        info = _process_service(svc, containers, processed)
        assert info.row_type == "Container Wrapper"
        assert "myapp" in processed

    def test_local_process(self):
        svc = SystemdService(name="ami-worker.service", pid="0")
        info = _process_service(svc, {}, set())
        assert info.row_type == "Local Process"


# ---------------------------------------------------------------------------
# status_utils additional functions
# ---------------------------------------------------------------------------


class TestStatusUtilsAdditional:
    """Test remaining status_utils functions."""

    def test_run_cmd_success(self):
        result = run_cmd("echo hello")
        assert "hello" in result

    def test_run_cmd_failure(self):
        result = run_cmd("nonexistent_command_xyz 2>/dev/null")
        assert result == ""

    def test_parse_size_to_bytes(self):
        assert parse_size_to_bytes("1024B") == EXPECTED_BYTES_1024
        assert parse_size_to_bytes("1K") == EXPECTED_BYTES_1024
        assert parse_size_to_bytes("1M") == EXPECTED_BYTES_1024**2
        assert parse_size_to_bytes("1G") == EXPECTED_BYTES_1024**3
        assert parse_size_to_bytes("") == 0
        assert parse_size_to_bytes("-") == 0
        assert parse_size_to_bytes("invalid") == 0

    def test_get_restart_icon(self):
        assert "\u267b" in _get_restart_icon("always")
        assert "\U0001fa79" in _get_restart_icon("on-failure")
        assert "\U0001f6ab" in _get_restart_icon("no")

    def test_get_container_status_display(self):
        icon, _color = _get_container_status_display("running")
        assert icon == "\U0001f7e2"
        icon, _color = _get_container_status_display("exited")
        assert icon == "\U0001f534"
        icon, _color = _get_container_status_display("unknown")
        assert icon == "\u26aa"

    def test_format_port_string(self):
        pm = PortMapping(host_port=8080, container_port=80, protocol="tcp")
        assert _format_port_string(pm) == "8080->80/tcp"

    def test_format_port_string_no_host(self):
        pm = PortMapping(container_port=80, protocol="tcp")
        assert _format_port_string(pm) == "80/tcp"

    def test_print_box_line(self, capsys):
        print_box_line("hello", 80)
        out = capsys.readouterr().out
        assert "hello" in out
        assert "\u2502" in out

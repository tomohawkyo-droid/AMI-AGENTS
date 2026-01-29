"""Unit tests for cli_components/status module."""

import subprocess
from unittest.mock import MagicMock, patch

from ami.cli_components.status import (
    DISPLAY_WIDTH,
    I_FAIL,
    I_OK,
    I_WARN,
    SYSTEMD_PREFIXES,
    _extract_compose_info,
    _parse_port_mapping,
    _parse_systemd_details,
    format_ports,
    get_local_ports,
    get_managed_service_names,
    get_visual_width,
    print_box_line,
    run_cmd,
)
from ami.types.common import PortData
from ami.types.status import PortMapping

EXPECTED_ASCII_WIDTH = 5
EXPECTED_ANSI_STRIPPED_WIDTH = 5
EXPECTED_CJK_WIDTH = 4
EXPECTED_HOST_PORT = 8080
EXPECTED_CONTAINER_PORT = 80
EXPECTED_HOST_PORT_SSL = 8080
EXPECTED_CONTAINER_PORT_SSL = 80
EXPECTED_DISPLAY_WIDTH_VALUE = 80
EXPECTED_MIN_PRINT_CALLS = 4
EXPECTED_MAX_OUTPUT_LENGTH = 300


class TestRunCmd:
    """Tests for run_cmd function."""

    @patch("ami.cli_components.status_utils.subprocess.run")
    def test_returns_stdout(self, mock_run) -> None:
        """Test returns stdout from command."""
        mock_run.return_value = MagicMock(stdout="output\n", returncode=0)

        result = run_cmd("echo output")

        assert result == "output"

    @patch("ami.cli_components.status_utils.subprocess.run")
    def test_strips_whitespace(self, mock_run) -> None:
        """Test strips whitespace from output."""
        mock_run.return_value = MagicMock(stdout="  output  \n", returncode=0)

        result = run_cmd("echo output")

        assert result == "output"

    @patch("ami.cli_components.status_utils.subprocess.run")
    def test_returns_empty_on_exception(self, mock_run) -> None:
        """Test returns empty string on SubprocessError."""
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        result = run_cmd("failing_command")

        assert result == ""


class TestGetVisualWidth:
    """Tests for get_visual_width function."""

    def test_ascii_text(self) -> None:
        """Test width of ASCII text."""
        assert get_visual_width("hello") == EXPECTED_ASCII_WIDTH

    def test_strips_ansi_codes(self) -> None:
        """Test strips ANSI escape codes."""
        text = "\033[32mgreen\033[0m"
        assert get_visual_width(text) == EXPECTED_ANSI_STRIPPED_WIDTH

    def test_wide_characters(self) -> None:
        """Test width of wide (CJK) characters."""
        text = "中文"
        assert get_visual_width(text) == EXPECTED_CJK_WIDTH  # Each CJK char is 2 cells

    def test_emoji_width(self) -> None:
        """Test emoji width handling."""
        text = "⚙️"
        width = get_visual_width(text)
        assert width >= 1


class TestGetLocalPorts:
    """Tests for get_local_ports function."""

    def test_returns_empty_for_zero_pid(self) -> None:
        """Test returns empty for pid 0."""
        result = get_local_ports("0")
        assert result == []

    def test_returns_empty_for_empty_pid(self) -> None:
        """Test returns empty for empty pid."""
        result = get_local_ports("")
        assert result == []

    @patch("ami.cli_components.status_utils.psutil", None)
    def test_returns_empty_without_psutil(self) -> None:
        """Test returns empty when psutil not available."""
        result = get_local_ports("1234")
        assert result == []


class TestFormatPorts:
    """Tests for format_ports function."""

    def test_empty_ports(self) -> None:
        """Test returns empty string for empty ports."""
        result = format_ports([])
        assert result == ""

    def test_host_and_container_port(self) -> None:
        """Test formats host->container port mapping."""
        ports = [PortMapping(hostPort=8080, containerPort=80, protocol="tcp")]

        result = format_ports(ports)

        assert result == "8080->80/tcp"

    def test_container_port_only(self) -> None:
        """Test formats container port only."""
        ports = [PortMapping(containerPort=80, protocol="tcp")]

        result = format_ports(ports)

        assert result == "80/tcp"

    def test_multiple_ports(self) -> None:
        """Test formats multiple port mappings."""
        ports = [
            PortMapping(hostPort=8080, containerPort=80, protocol="tcp"),
            PortMapping(hostPort=8443, containerPort=443, protocol="tcp"),
        ]

        result = format_ports(ports)

        assert "8080->80/tcp" in result
        assert "8443->443/tcp" in result


class TestParseSystemdDetails:
    """Tests for _parse_systemd_details function."""

    def test_parses_key_value_pairs(self) -> None:
        """Test parses key=value pairs."""
        raw = "Id=test.service\nActiveState=active\nSubState=running"

        result = _parse_systemd_details(raw)

        assert result["Id"] == "test.service"
        assert result["ActiveState"] == "active"
        assert result["SubState"] == "running"

    def test_handles_empty_values(self) -> None:
        """Test handles empty values."""
        raw = "Id="

        result = _parse_systemd_details(raw)

        assert result["Id"] == ""

    def test_handles_values_with_equals(self) -> None:
        """Test handles values containing equals sign."""
        raw = "ExecStart=foo=bar=baz"

        result = _parse_systemd_details(raw)

        assert result["ExecStart"] == "foo=bar=baz"


class TestExtractComposeInfo:
    """Tests for _extract_compose_info function."""

    def test_extracts_container_from_podman_start(self) -> None:
        """Test extracts container name from podman start."""
        exec_start = "podman start --attach mycontainer"

        container, _compose_file, _profiles = _extract_compose_info(exec_start)

        assert container == "mycontainer"

    def test_extracts_compose_file(self) -> None:
        """Test extracts compose file from podman-compose."""
        exec_start = "podman-compose -f docker-compose.yml up"

        _, compose_file, _ = _extract_compose_info(exec_start)

        assert compose_file == "docker-compose.yml"

    def test_extracts_profiles(self) -> None:
        """Test extracts profiles from podman-compose."""
        exec_start = "podman-compose --profile dev --profile test up"

        _, _, profiles = _extract_compose_info(exec_start)

        assert profiles == ["dev", "test"]

    def test_returns_none_for_no_match(self) -> None:
        """Test returns None values when no patterns match."""
        exec_start = "python script.py"

        container, compose_file, profiles = _extract_compose_info(exec_start)

        assert container is None
        assert compose_file is None
        assert profiles == []


class TestParsePortMapping:
    """Tests for _parse_port_mapping function."""

    def test_parses_camel_case_keys(self) -> None:
        """Test parses camelCase keys."""
        data: PortData = {"hostPort": 8080, "containerPort": 80, "protocol": "tcp"}

        result = _parse_port_mapping(data)

        assert result.host_port == EXPECTED_HOST_PORT
        assert result.container_port == EXPECTED_CONTAINER_PORT
        assert result.protocol == "tcp"

    def test_parses_pascal_case_keys(self) -> None:
        """Test parses PascalCase keys."""
        data: PortData = {"HostPort": 8080, "ContainerPort": 80, "Protocol": "udp"}

        result = _parse_port_mapping(data)

        assert result.host_port == EXPECTED_HOST_PORT
        assert result.container_port == EXPECTED_CONTAINER_PORT
        assert result.protocol == "udp"

    def test_parses_snake_case_keys(self) -> None:
        """Test parses snake_case keys."""
        data: PortData = {"host_port": 8080, "container_port": 80}

        result = _parse_port_mapping(data)

        assert result.host_port == EXPECTED_HOST_PORT
        assert result.container_port == EXPECTED_CONTAINER_PORT

    def test_defaults_protocol_to_tcp(self) -> None:
        """Test defaults protocol to tcp."""
        data: PortData = {"hostPort": 8080, "containerPort": 80}

        result = _parse_port_mapping(data)

        assert result.protocol == "tcp"


class TestGetManagedServiceNames:
    """Tests for get_managed_service_names function."""

    @patch("ami.cli_components.status_systemd.yaml", None)
    def test_returns_empty_without_yaml(self) -> None:
        """Test returns empty set when yaml not available."""
        result = get_managed_service_names()
        assert result == set()

    @patch("ami.cli_components.status_systemd.yaml")
    def test_returns_empty_when_file_not_found(self, mock_yaml) -> None:
        """Test returns empty set when inventory file not found."""
        with patch("pathlib.Path.exists", return_value=False):
            result = get_managed_service_names()
        assert result == set()


class TestPrintBoxLine:
    """Tests for print_box_line function."""

    def test_prints_formatted_line(self, capsys) -> None:
        """Test prints formatted box line."""
        print_box_line("test", DISPLAY_WIDTH)

        captured = capsys.readouterr()
        assert "│" in captured.out
        assert "test" in captured.out

    def test_truncates_long_text(self, capsys) -> None:
        """Test truncates text that's too long."""
        long_text = "x" * 200

        print_box_line(long_text, DISPLAY_WIDTH)

        captured = capsys.readouterr()
        # Should not exceed display width
        assert len(captured.out.strip()) < EXPECTED_MAX_OUTPUT_LENGTH


class TestConstants:
    """Tests for module constants."""

    def test_display_width(self) -> None:
        """Test DISPLAY_WIDTH is set."""
        assert DISPLAY_WIDTH == EXPECTED_DISPLAY_WIDTH_VALUE

    def test_systemd_prefixes(self) -> None:
        """Test SYSTEMD_PREFIXES contains expected prefixes."""
        assert "ami-" in SYSTEMD_PREFIXES
        assert "postgres" in SYSTEMD_PREFIXES

    def test_icons_defined(self) -> None:
        """Test icons are defined."""
        assert I_OK == "🟢"
        assert I_FAIL == "🔴"
        assert I_WARN == "🟡"

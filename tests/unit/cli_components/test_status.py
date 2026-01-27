"""Unit tests for ami/cli_components/status.py."""

import subprocess
from unittest.mock import MagicMock, patch

from ami.cli_components.status import (
    DISPLAY_WIDTH,
    I_BOOT,
    I_FAIL,
    I_NOBOOT,
    I_NORESTART,
    I_OK,
    I_RESTART_ALWAYS,
    I_RESTART_FAIL,
    I_STOP,
    I_WARN,
    SYSTEMD_PREFIXES,
    _extract_compose_info,
    _get_restart_icon,
    _parse_port_mapping,
    _parse_systemd_details,
    format_bytes,
    format_ports,
    get_visual_width,
    parse_size_to_bytes,
    run_cmd,
)
from ami.types.status import PortMapping

EXPECTED_ASCII_WIDTH = 5
EXPECTED_ANSI_STRIPPED_WIDTH = 5
EXPECTED_PARSED_BYTES_100 = 100
EXPECTED_PARSED_1K = 1024
EXPECTED_PARSED_2K = 2048
EXPECTED_HOST_PORT_8080 = 8080
EXPECTED_CONTAINER_PORT_80 = 80
EXPECTED_PORT_443 = 443
EXPECTED_DISPLAY_WIDTH_VALUE = 80


class TestRunCmd:
    """Tests for run_cmd function."""

    @patch("ami.cli_components.status_utils.subprocess.run")
    def test_returns_stdout(self, mock_run):
        """Test returns stdout from command."""
        mock_run.return_value = MagicMock(stdout="  output  ")
        result = run_cmd("echo test")
        assert result == "output"

    @patch("ami.cli_components.status_utils.subprocess.run")
    def test_returns_empty_on_error(self, mock_run):
        """Test returns empty string on subprocess error."""
        mock_run.side_effect = subprocess.SubprocessError("Command failed")
        result = run_cmd("invalid")
        assert result == ""


class TestGetVisualWidth:
    """Tests for get_visual_width function."""

    def test_simple_ascii(self):
        """Test width of simple ASCII text."""
        assert get_visual_width("hello") == EXPECTED_ASCII_WIDTH
        assert get_visual_width("") == 0

    def test_strips_ansi_codes(self):
        """Test ANSI codes don't contribute to width."""
        assert get_visual_width("\033[32mgreen\033[0m") == EXPECTED_ANSI_STRIPPED_WIDTH

    def test_gear_emoji_correction(self):
        """Test gear emoji width correction."""
        # Gear emoji needs width correction
        text = "⚙️ settings"
        width = get_visual_width(text)
        assert width > len("settings")


class TestFormatPorts:
    """Tests for format_ports function."""

    def test_empty_ports(self):
        """Test with no ports."""
        assert format_ports([]) == ""

    def test_single_port_with_both(self):
        """Test single port with host and container."""
        ports = [PortMapping(host_port=8080, container_port=80, protocol="tcp")]
        result = format_ports(ports)
        assert result == "8080->80/tcp"

    def test_single_port_container_only(self):
        """Test single port with only container port."""
        ports = [PortMapping(container_port=80, protocol="tcp")]
        result = format_ports(ports)
        assert result == "80/tcp"

    def test_multiple_ports(self):
        """Test multiple port mappings."""
        ports = [
            PortMapping(host_port=8080, container_port=80, protocol="tcp"),
            PortMapping(host_port=443, container_port=443, protocol="tcp"),
        ]
        result = format_ports(ports)
        assert "8080->80/tcp" in result
        assert "443->443/tcp" in result
        assert ", " in result

    def test_udp_protocol(self):
        """Test UDP protocol display."""
        ports = [PortMapping(host_port=53, container_port=53, protocol="udp")]
        result = format_ports(ports)
        assert result == "53->53/udp"


class TestFormatBytes:
    """Tests for format_bytes function."""

    def test_zero_bytes(self):
        """Test formatting zero bytes."""
        assert format_bytes(0) == "0B"
        assert format_bytes(-10) == "0B"

    def test_bytes(self):
        """Test formatting small byte values."""
        assert format_bytes(100) == "100B"
        assert format_bytes(500) == "500B"

    def test_kilobytes(self):
        """Test formatting kilobyte values."""
        assert format_bytes(1024) == "1KB"
        assert format_bytes(2048) == "2KB"

    def test_megabytes(self):
        """Test formatting megabyte values."""
        result = format_bytes(1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        """Test formatting gigabyte values."""
        result = format_bytes(1024 * 1024 * 1024)
        assert "GB" in result

    def test_terabytes(self):
        """Test formatting terabyte values."""
        result = format_bytes(1024**4)
        assert "TB" in result


class TestParseSizeToBytes:
    """Tests for parse_size_to_bytes function."""

    def test_empty_string(self):
        """Test parsing empty string."""
        assert parse_size_to_bytes("") == 0
        assert parse_size_to_bytes("-") == 0

    def test_bytes(self):
        """Test parsing byte values."""
        assert parse_size_to_bytes("100B") == EXPECTED_PARSED_BYTES_100
        assert parse_size_to_bytes("100b") == EXPECTED_PARSED_BYTES_100

    def test_kilobytes(self):
        """Test parsing kilobyte values."""
        assert parse_size_to_bytes("1K") == EXPECTED_PARSED_1K
        assert parse_size_to_bytes("2K") == EXPECTED_PARSED_2K

    def test_megabytes(self):
        """Test parsing megabyte values."""
        assert parse_size_to_bytes("1M") == 1024 * 1024

    def test_gigabytes(self):
        """Test parsing gigabyte values."""
        assert parse_size_to_bytes("1G") == 1024**3

    def test_decimal_values(self):
        """Test parsing decimal values."""
        result = parse_size_to_bytes("1.5M")
        assert result == int(1.5 * 1024 * 1024)

    def test_invalid_value(self):
        """Test parsing invalid value."""
        assert parse_size_to_bytes("invalid") == 0


class TestParseSystemdDetails:
    """Tests for _parse_systemd_details function."""

    def test_parses_key_value_pairs(self):
        """Test parsing key=value pairs."""
        raw = "Id=test.service\nActiveState=active\nMainPID=1234"
        result = _parse_systemd_details(raw)
        assert result["Id"] == "test.service"
        assert result["ActiveState"] == "active"
        assert result["MainPID"] == "1234"

    def test_handles_empty_values(self):
        """Test handling empty values."""
        raw = "Key1=\nKey2=value2"
        result = _parse_systemd_details(raw)
        assert result["Key1"] == ""
        assert result["Key2"] == "value2"

    def test_handles_values_with_equals(self):
        """Test handling values containing equals sign."""
        raw = "ExecStart=/bin/command --arg=value"
        result = _parse_systemd_details(raw)
        assert result["ExecStart"] == "/bin/command --arg=value"


class TestExtractComposeInfo:
    """Tests for _extract_compose_info function."""

    def test_extracts_container_name(self):
        """Test extracting container name from podman start."""
        exec_start = "podman start --attach my-container"
        container, compose_file, profiles = _extract_compose_info(exec_start)
        assert container == "my-container"
        assert compose_file is None
        assert profiles == []

    def test_extracts_compose_file(self):
        """Test extracting compose file."""
        exec_start = "podman-compose -f docker-compose.yml up"
        _container, compose_file, _profiles = _extract_compose_info(exec_start)
        assert compose_file == "docker-compose.yml"

    def test_extracts_profiles(self):
        """Test extracting compose profiles."""
        exec_start = "podman-compose -f compose.yml --profile dev --profile test up"
        _container, _compose_file, profiles = _extract_compose_info(exec_start)
        assert profiles == ["dev", "test"]

    def test_no_compose(self):
        """Test when not using compose."""
        exec_start = "/usr/bin/some-daemon"
        container, compose_file, profiles = _extract_compose_info(exec_start)
        assert container is None
        assert compose_file is None
        assert profiles == []


class TestGetRestartIcon:
    """Tests for _get_restart_icon function."""

    def test_always_restart(self):
        """Test icon for always restart policy."""
        assert _get_restart_icon("always") == I_RESTART_ALWAYS

    def test_on_failure_restart(self):
        """Test icon for on-failure restart policy."""
        assert _get_restart_icon("on-failure") == I_RESTART_FAIL
        assert _get_restart_icon("on-abnormal") == I_RESTART_FAIL
        assert _get_restart_icon("on-abort") == I_RESTART_FAIL
        assert _get_restart_icon("on-watchdog") == I_RESTART_FAIL

    def test_no_restart(self):
        """Test icon for no restart policy."""
        assert _get_restart_icon("no") == I_NORESTART
        assert _get_restart_icon("") == I_NORESTART
        assert _get_restart_icon("unknown") == I_NORESTART


class TestParsePortMapping:
    """Tests for _parse_port_mapping function."""

    def test_parses_standard_format(self):
        """Test parsing standard port mapping."""
        data = {"hostPort": 8080, "containerPort": 80, "protocol": "tcp"}
        result = _parse_port_mapping(data)
        assert result.host_port == EXPECTED_HOST_PORT_8080
        assert result.container_port == EXPECTED_CONTAINER_PORT_80
        assert result.protocol == "tcp"

    def test_parses_alternate_keys(self):
        """Test parsing with alternate key names."""
        data = {"HostPort": 8080, "ContainerPort": 80, "Protocol": "udp"}
        result = _parse_port_mapping(data)
        assert result.host_port == EXPECTED_HOST_PORT_8080
        assert result.container_port == EXPECTED_CONTAINER_PORT_80
        assert result.protocol == "udp"

    def test_parses_snake_case_keys(self):
        """Test parsing with snake_case keys."""
        data = {"host_port": 443, "container_port": 443}
        result = _parse_port_mapping(data)
        assert result.host_port == EXPECTED_PORT_443
        assert result.container_port == EXPECTED_PORT_443

    def test_default_protocol(self):
        """Test default protocol is tcp."""
        data = {"hostPort": 80, "containerPort": 80}
        result = _parse_port_mapping(data)
        assert result.protocol == "tcp"


class TestConstants:
    """Tests for module constants."""

    def test_display_width(self):
        """Test DISPLAY_WIDTH is reasonable."""
        assert DISPLAY_WIDTH == EXPECTED_DISPLAY_WIDTH_VALUE

    def test_status_icons_are_defined(self):
        """Test status icons are defined."""
        assert I_OK == "🟢"
        assert I_FAIL == "🔴"
        assert I_WARN == "🟡"
        assert I_STOP == "⚪"

    def test_boot_icons_are_defined(self):
        """Test boot icons are defined."""
        assert I_BOOT == "🚀"
        assert I_NOBOOT == "💤"

    def test_systemd_prefixes(self):
        """Test SYSTEMD_PREFIXES contains expected prefixes."""
        assert "ami-" in SYSTEMD_PREFIXES
        assert "postgres" in SYSTEMD_PREFIXES
        assert "traefik" in SYSTEMD_PREFIXES

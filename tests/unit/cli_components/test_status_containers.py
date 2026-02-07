"""Unit tests for ami/cli_components/status_containers.py."""

import json
from unittest.mock import patch

from ami.cli_components.status_containers import (
    _find_size_by_name,
    _find_stats_by_name,
    _get_container_inspect_info,
    get_container_sizes,
    get_container_stats,
    get_container_volumes,
    get_podman_containers,
    get_system_docker_containers,
    get_system_docker_stats,
)
from ami.types.common import ContainerSizeData, ContainerStatsData

EXPECTED_CPU_15 = "15%"
EXPECTED_MEM_100M = "100MiB / 8GiB"
EXPECTED_MEM_PERCENT_1 = "1.25%"
EXPECTED_EXPOSED_PORTS_COUNT = 2
EXPECTED_HOST_PORT_8080 = 8080


class TestFindStatsByName:
    """Tests for _find_stats_by_name function."""

    def test_finds_existing_entry(self):
        """Test finds stats by name."""
        stats: list[ContainerStatsData] = [
            ContainerStatsData(
                name="web", cpu="10%", mem_usage="100M", mem_percent="5%"
            ),
            ContainerStatsData(
                name="db", cpu="20%", mem_usage="500M", mem_percent="10%"
            ),
        ]
        result = _find_stats_by_name(stats, "db")
        assert result is not None
        assert result["name"] == "db"

    def test_returns_none_when_not_found(self):
        """Test returns None when name not found."""
        stats: list[ContainerStatsData] = [
            ContainerStatsData(
                name="web", cpu="10%", mem_usage="100M", mem_percent="5%"
            ),
        ]
        result = _find_stats_by_name(stats, "missing")
        assert result is None

    def test_empty_list(self):
        """Test with empty list."""
        assert _find_stats_by_name([], "any") is None


class TestFindSizeByName:
    """Tests for _find_size_by_name function."""

    def test_finds_existing_entry(self):
        """Test finds size by name."""
        sizes: list[ContainerSizeData] = [
            ContainerSizeData(name="web", writable="22kB", virtual="198MB"),
        ]
        result = _find_size_by_name(sizes, "web")
        assert result is not None
        assert result["writable"] == "22kB"

    def test_returns_none_when_not_found(self):
        """Test returns None when name not found."""
        sizes: list[ContainerSizeData] = [
            ContainerSizeData(name="web", writable="22kB", virtual="198MB"),
        ]
        assert _find_size_by_name(sizes, "missing") is None


class TestGetContainerInspectInfo:
    """Tests for _get_container_inspect_info function."""

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_returns_empty_when_no_output(self, mock_cmd):
        """Test returns empty when no inspect output."""
        mock_cmd.return_value = ""
        result = _get_container_inspect_info("test", "podman")
        assert result.ports == []
        assert result.labels == {}

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_parses_exposed_ports(self, mock_cmd):
        """Test parses exposed ports from inspect data."""
        inspect_data = [
            {
                "Config": {
                    "ExposedPorts": {"80/tcp": {}, "443/tcp": {}},
                    "Labels": {"app": "web"},
                }
            }
        ]
        mock_cmd.return_value = json.dumps(inspect_data)
        result = _get_container_inspect_info("test", "podman")
        assert len(result.ports) == EXPECTED_EXPOSED_PORTS_COUNT
        assert result.labels["app"] == "web"

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_handles_empty_json_array(self, mock_cmd):
        """Test handles empty JSON array."""
        mock_cmd.return_value = "[]"
        result = _get_container_inspect_info("test", "podman")
        assert result.ports == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_handles_invalid_json(self, mock_cmd):
        """Test handles invalid JSON gracefully."""
        mock_cmd.return_value = "not json"
        result = _get_container_inspect_info("test", "podman")
        assert result.ports == []


class TestGetContainerStats:
    """Tests for get_container_stats function."""

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_returns_empty_when_no_output(self, mock_cmd):
        """Test returns empty list when no output."""
        mock_cmd.return_value = ""
        assert get_container_stats() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_parses_stats_data(self, mock_cmd):
        """Test parses container stats from JSON."""
        stats_data = [
            {
                "Name": "web",
                "CPU": EXPECTED_CPU_15,
                "MemUsage": EXPECTED_MEM_100M,
                "MemPerc": EXPECTED_MEM_PERCENT_1,
            }
        ]
        mock_cmd.return_value = json.dumps(stats_data)
        result = get_container_stats()
        assert len(result) == 1
        assert result[0]["name"] == "web"
        assert result[0]["cpu"] == EXPECTED_CPU_15

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_skips_entries_without_name(self, mock_cmd):
        """Test skips entries without a name."""
        stats_data = [{"CPU": "10%"}]
        mock_cmd.return_value = json.dumps(stats_data)
        assert get_container_stats() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_handles_invalid_json(self, mock_cmd):
        """Test handles invalid JSON gracefully."""
        mock_cmd.return_value = "not json"
        assert get_container_stats() == []


class TestGetContainerSizes:
    """Tests for get_container_sizes function."""

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_returns_empty_when_no_output(self, mock_cmd):
        """Test returns empty list when no output."""
        mock_cmd.return_value = ""
        assert get_container_sizes() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_parses_size_with_virtual(self, mock_cmd):
        """Test parses size string with virtual component."""
        mock_cmd.return_value = "web\t22kB (virtual 198MB)"
        result = get_container_sizes()
        assert len(result) == 1
        assert result[0]["name"] == "web"
        assert result[0]["writable"] == "22kB"
        assert result[0]["virtual"] == "198MB"

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_parses_size_without_virtual(self, mock_cmd):
        """Test parses size string without virtual component."""
        mock_cmd.return_value = "web\t22kB"
        result = get_container_sizes()
        assert len(result) == 1
        assert result[0]["writable"] == "22kB"

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_skips_malformed_lines(self, mock_cmd):
        """Test skips lines without tab separator."""
        mock_cmd.return_value = "no-tab-here"
        assert get_container_sizes() == []


class TestGetContainerVolumes:
    """Tests for get_container_volumes function."""

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_returns_empty_when_no_output(self, mock_cmd):
        """Test returns empty list when no inspect output."""
        mock_cmd.return_value = ""
        assert get_container_volumes("test") == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_returns_empty_for_empty_json(self, mock_cmd):
        """Test returns empty for empty JSON array."""
        mock_cmd.return_value = "[]"
        assert get_container_volumes("test") == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_parses_volume_mounts(self, mock_cmd):
        """Test parses volume mount data."""
        inspect_data = [
            {
                "Mounts": [
                    {
                        "Source": "/host/data",
                        "Destination": "/container/data",
                        "Type": "bind",
                    }
                ]
            }
        ]
        # First call: inspect, subsequent calls: du for size
        mock_cmd.side_effect = [json.dumps(inspect_data), "65536"]
        result = get_container_volumes("test")
        assert len(result) == 1
        assert result[0]["dst"] == "/container/data"

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_skips_small_volumes(self, mock_cmd):
        """Test skips volumes smaller than threshold."""
        inspect_data = [
            {
                "Mounts": [
                    {
                        "Source": "/host/data",
                        "Destination": "/container/data",
                        "Type": "bind",
                    }
                ]
            }
        ]
        mock_cmd.side_effect = [json.dumps(inspect_data), "100"]
        result = get_container_volumes("test")
        assert len(result) == 0

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_skips_mounts_without_destination(self, mock_cmd):
        """Test skips mounts without destination."""
        inspect_data = [{"Mounts": [{"Source": "/host/data", "Type": "bind"}]}]
        mock_cmd.side_effect = [json.dumps(inspect_data)]
        result = get_container_volumes("test")
        assert len(result) == 0


class TestGetPodmanContainers:
    """Tests for get_podman_containers function."""

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_returns_empty_when_no_output(self, mock_cmd):
        """Test returns empty list when no podman output."""
        mock_cmd.return_value = ""
        assert get_podman_containers() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_parses_container_data(self, mock_cmd):
        """Test parses podman container JSON."""
        container_data = [
            {
                "Id": "abc123def456",
                "Names": ["web"],
                "State": "running",
                "Status": "Up 2 hours",
                "Ports": [],
                "Image": "nginx:1.27",
            }
        ]
        # First call: ps -a, second call: inspect
        mock_cmd.side_effect = [json.dumps(container_data), ""]
        result = get_podman_containers()
        assert len(result) == 1
        assert result[0].name == "web"
        assert result[0].state == "running"

    @patch("ami.cli_components.status_containers.run_cmd")
    def test_handles_invalid_json(self, mock_cmd):
        """Test handles invalid JSON gracefully."""
        mock_cmd.return_value = "not json"
        assert get_podman_containers() == []


class TestGetSystemDockerContainers:
    """Tests for get_system_docker_containers function."""

    @patch("os.path.exists", return_value=False)
    def test_returns_empty_when_no_docker(self, mock_exists):
        """Test returns empty when docker binary not found."""
        assert get_system_docker_containers() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    @patch("os.path.exists", return_value=True)
    def test_returns_empty_when_no_output(self, mock_exists, mock_cmd):
        """Test returns empty when docker returns no output."""
        mock_cmd.return_value = ""
        assert get_system_docker_containers() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    @patch("os.path.exists", return_value=True)
    def test_parses_docker_json_per_line(self, mock_exists, mock_cmd):
        """Test parses Docker's per-line JSON format."""
        line = json.dumps(
            {
                "ID": "abc123def456",
                "Names": "web",
                "State": "running",
                "Status": "Up 2 hours",
                "Ports": "0.0.0.0:8080->80/tcp",
                "Image": "nginx",
            }
        )
        mock_cmd.return_value = line
        result = get_system_docker_containers()
        assert len(result) == 1
        assert result[0].name == "web"
        assert len(result[0].ports) == 1
        assert result[0].ports[0].host_port == EXPECTED_HOST_PORT_8080

    @patch("ami.cli_components.status_containers.run_cmd")
    @patch("os.path.exists", return_value=True)
    def test_handles_no_ports(self, mock_exists, mock_cmd):
        """Test handles containers with no ports."""
        line = json.dumps(
            {
                "ID": "abc123def456",
                "Names": "worker",
                "State": "running",
                "Status": "Up",
                "Ports": "",
                "Image": "worker:1.0",
            }
        )
        mock_cmd.return_value = line
        result = get_system_docker_containers()
        assert len(result) == 1
        assert result[0].ports == []


class TestGetSystemDockerStats:
    """Tests for get_system_docker_stats function."""

    @patch("os.path.exists", return_value=False)
    def test_returns_empty_when_no_docker(self, mock_exists):
        """Test returns empty when docker binary not found."""
        assert get_system_docker_stats() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    @patch("os.path.exists", return_value=True)
    def test_returns_empty_when_no_output(self, mock_exists, mock_cmd):
        """Test returns empty when no stats output."""
        mock_cmd.return_value = ""
        assert get_system_docker_stats() == []

    @patch("ami.cli_components.status_containers.run_cmd")
    @patch("os.path.exists", return_value=True)
    def test_parses_stats_output(self, mock_exists, mock_cmd):
        """Test parses pipe-delimited stats output."""
        mock_cmd.return_value = "web|15.2%|100MiB / 8GiB"
        result = get_system_docker_stats()
        assert len(result) == 1
        assert result[0]["name"] == "web"
        assert result[0]["cpu"] == "15.2%"

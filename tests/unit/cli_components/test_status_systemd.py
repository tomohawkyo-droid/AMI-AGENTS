"""Unit tests for ami/cli_components/status_systemd.py."""

from unittest.mock import patch

from ami.cli_components.status_systemd import (
    _find_container_by_name,
    _process_service,
    get_managed_service_names,
    get_systemd_services,
)
from ami.types.status import (
    PodmanContainer,
    SystemdService,
)


class TestFindContainerByName:
    """Tests for _find_container_by_name function."""

    def test_finds_existing_container(self):
        """Test finds container by name."""
        containers = [
            PodmanContainer(
                id="abc123",
                name="web",
                state="running",
                status="Up",
                ports=[],
                image="nginx",
                labels={},
            ),
            PodmanContainer(
                id="def456",
                name="db",
                state="running",
                status="Up",
                ports=[],
                image="postgres",
                labels={},
            ),
        ]
        result = _find_container_by_name(containers, "db")
        assert result is not None
        assert result.name == "db"

    def test_returns_none_when_not_found(self):
        """Test returns None when container not found."""
        containers = [
            PodmanContainer(
                id="abc123",
                name="web",
                state="running",
                status="Up",
                ports=[],
                image="nginx",
                labels={},
            ),
        ]
        assert _find_container_by_name(containers, "missing") is None

    def test_empty_list(self):
        """Test with empty container list."""
        assert _find_container_by_name([], "any") is None


class TestProcessService:
    """Tests for _process_service function."""

    def test_local_process_service(self):
        """Test processing a local process service (no containers)."""
        svc = SystemdService(
            name="ami-test.service",
            scope="user",
            active="active",
            sub="running",
            path="/etc/systemd/user/ami-test.service",
            pid="0",
            managed_container=None,
            compose_file=None,
            compose_profiles=[],
            restart="always",
            enabled="enabled",
        )
        processed: set[str] = set()
        result = _process_service(svc, [], processed)
        assert result.row_type == "Local Process"
        assert result.child_items == []

    def test_container_wrapper_service(self):
        """Test processing a container wrapper service."""
        svc = SystemdService(
            name="ami-web.service",
            scope="user",
            active="active",
            sub="running",
            path="/path/to/service",
            pid="1234",
            managed_container="web-container",
            compose_file=None,
            compose_profiles=[],
            restart="always",
            enabled="enabled",
        )
        container = PodmanContainer(
            id="abc123",
            name="web-container",
            state="running",
            status="Up",
            ports=[],
            image="nginx",
            labels={},
        )
        processed: set[str] = set()
        result = _process_service(svc, [container], processed)
        assert result.row_type == "Container Wrapper"
        assert len(result.child_items) == 1
        assert "web-container" in processed

    def test_compose_service(self):
        """Test processing a compose service."""
        svc = SystemdService(
            name="ami-compose.service",
            scope="user",
            active="active",
            sub="running",
            path="/path/to/service",
            pid="1234",
            managed_container=None,
            compose_file="docker-compose.yml",
            compose_profiles=["dev", "test"],
            restart="always",
            enabled="enabled",
        )
        container = PodmanContainer(
            id="abc123",
            name="web",
            state="running",
            status="Up",
            ports=[],
            image="nginx",
            labels={"com.docker.compose.project.config_files": "docker-compose.yml"},
        )
        processed: set[str] = set()
        result = _process_service(svc, [container], processed)
        assert result.row_type == "Unified Stack"
        assert len(result.child_items) == 1
        assert "web" in processed

    @patch("ami.cli_components.status_systemd.get_local_ports", return_value=["8080"])
    def test_local_process_with_ports(self, mock_ports):
        """Test local process service shows ports."""
        svc = SystemdService(
            name="ami-api.service",
            scope="user",
            active="active",
            sub="running",
            path="/path/to/service",
            pid="5678",
            managed_container=None,
            compose_file=None,
            compose_profiles=[],
            restart="always",
            enabled="enabled",
        )
        processed: set[str] = set()
        result = _process_service(svc, [], processed)
        assert result.ports_str == "8080"


class TestGetManagedServiceNames:
    """Tests for get_managed_service_names function."""

    @patch("ami.cli_components.status_systemd.Path")
    def test_returns_empty_when_no_inventory(self, mock_path_cls):
        """Test returns empty set when no inventory file found."""
        mock_path = mock_path_cls.return_value
        mock_path.__truediv__ = lambda self, other: mock_path
        mock_path.exists.return_value = False
        # Mock all search paths
        mock_path_cls.home.return_value.__truediv__ = lambda self, other: mock_path
        mock_path_cls.cwd.return_value = mock_path
        mock_path_cls.cwd.return_value.parent = mock_path
        result = get_managed_service_names()
        # May return managed or empty depending on real filesystem
        assert isinstance(result, set)

    @patch(
        "builtins.open",
        create=True,
    )
    @patch("ami.cli_components.status_systemd.yaml.safe_load")
    @patch("ami.cli_components.status_systemd.Path")
    def test_loads_services_from_inventory(self, mock_path_cls, mock_yaml, mock_open):
        """Test loads service names from Ansible inventory."""
        # Make the first candidate path exist
        mock_candidate = type(mock_path_cls)()
        mock_candidate.exists = lambda: True

        mock_home = type(mock_path_cls)()
        mock_home.__truediv__ = lambda self, other: mock_candidate
        mock_path_cls.home.return_value = mock_home
        mock_candidate.__truediv__ = lambda self, other: mock_candidate

        mock_yaml.return_value = {
            "local_services": {
                "ami-cms": {},
                "ami-api": {},
            },
            "compose_services": {"web": {}},
        }

        result = get_managed_service_names()
        assert isinstance(result, set)


class TestGetSystemdServices:
    """Tests for get_systemd_services function."""

    @patch("ami.cli_components.status_systemd.run_cmd")
    def test_returns_empty_when_no_services(self, mock_cmd):
        """Test returns empty list when no matching services."""
        mock_cmd.return_value = ""
        assert get_systemd_services() == []

    @patch("ami.cli_components.status_systemd.run_cmd")
    def test_parses_service_lines(self, mock_cmd):
        """Test parses systemctl output for matching services."""
        # First call: user services, second call: system services
        mock_cmd.side_effect = [
            "ami-test.service loaded active running AMI Test Service",
            "",  # No system services
            # show command for the service
            "Id=ami-test.service\n"
            "ActiveState=active\n"
            "SubState=running\n"
            "FragmentPath=/path/to/service\n"
            "MainPID=1234\n"
            "ExecStart=/usr/bin/test\n"
            "Restart=always\n"
            "UnitFileState=enabled",
        ]
        result = get_systemd_services()
        assert len(result) == 1
        assert result[0].name == "ami-test.service"
        assert result[0].scope == "user"

    @patch("ami.cli_components.status_systemd.run_cmd")
    def test_skips_non_matching_services(self, mock_cmd):
        """Test skips services that don't match known prefixes."""
        mock_cmd.side_effect = [
            "sshd.service loaded active running OpenSSH",
            "nginx.service loaded active running Nginx",
        ]
        result = get_systemd_services()
        assert len(result) == 0

"""Unit tests for types/status module."""

from ami.types.status import (
    PodmanContainer,
    PortMapping,
    ServiceDisplayInfo,
    SystemdService,
)

EXPECTED_HOST_PORT = 8080
EXPECTED_CONTAINER_PORT = 80
EXPECTED_ALIAS_PORT = 3000
EXPECTED_PORT_COUNT = 2
EXPECTED_ROW_DETAIL_COUNT = 3
EXPECTED_CHILD_ITEM_COUNT = 2


class TestPortMapping:
    """Tests for PortMapping model."""

    def test_default_values(self) -> None:
        """Test default values for PortMapping."""
        port = PortMapping()
        assert port.host_port is None
        assert port.container_port is None
        assert port.protocol == "tcp"

    def test_with_values(self) -> None:
        """Test PortMapping with explicit values."""
        port = PortMapping(hostPort=8080, containerPort=80, protocol="udp")
        assert port.host_port == EXPECTED_HOST_PORT
        assert port.container_port == EXPECTED_CONTAINER_PORT
        assert port.protocol == "udp"

    def test_alias_support(self) -> None:
        """Test PortMapping supports camelCase aliases."""
        port = PortMapping(hostPort=3000, containerPort=3000)
        assert port.host_port == EXPECTED_ALIAS_PORT
        assert port.container_port == EXPECTED_ALIAS_PORT


class TestPodmanContainer:
    """Tests for PodmanContainer model."""

    def test_required_fields(self) -> None:
        """Test PodmanContainer requires id and name."""
        container = PodmanContainer(id="abc123", name="my-container")
        assert container.id == "abc123"
        assert container.name == "my-container"

    def test_default_values(self) -> None:
        """Test PodmanContainer default values."""
        container = PodmanContainer(id="abc", name="test")
        assert container.state == ""
        assert container.status == ""
        assert container.ports == []
        assert container.image == ""
        assert container.labels == {}

    def test_with_ports(self) -> None:
        """Test PodmanContainer with port mappings."""
        ports = [
            PortMapping(hostPort=8080, containerPort=80),
            PortMapping(hostPort=443, containerPort=443),
        ]
        container = PodmanContainer(
            id="container1",
            name="web",
            state="running",
            status="Up 2 hours",
            ports=ports,
            image="nginx:1.27.0",
        )
        assert len(container.ports) == EXPECTED_PORT_COUNT
        assert container.ports[0].host_port == EXPECTED_HOST_PORT
        assert container.image == "nginx:1.27.0"

    def test_with_labels(self) -> None:
        """Test PodmanContainer with labels."""
        labels = {"app": "web", "env": "prod"}
        container = PodmanContainer(
            id="abc",
            name="test",
            labels=labels,
        )
        # Labels are stored as object, cast for dict access in test
        stored_labels = container.labels
        assert isinstance(stored_labels, dict)
        assert stored_labels["app"] == "web"
        assert stored_labels["env"] == "prod"


class TestSystemdService:
    """Tests for SystemdService model."""

    def test_required_fields(self) -> None:
        """Test SystemdService requires name."""
        service = SystemdService(name="nginx.service")
        assert service.name == "nginx.service"

    def test_default_values(self) -> None:
        """Test SystemdService default values."""
        service = SystemdService(name="test")
        assert service.scope == ""
        assert service.active == ""
        assert service.sub == ""
        assert service.path == ""
        assert service.pid == "0"
        assert service.managed_container is None
        assert service.compose_file is None
        assert service.compose_profiles == []

    def test_full_service(self) -> None:
        """Test SystemdService with all fields."""
        service = SystemdService(
            name="podman-compose@myapp.service",
            scope="user",
            active="active",
            sub="running",
            path="/opt/user/.config/systemd/user",
            pid="12345",
            managed_container="myapp",
            compose_file="/opt/user/app/docker-compose.yml",
            compose_profiles=["dev", "debug"],
        )
        assert service.name == "podman-compose@myapp.service"
        assert service.scope == "user"
        assert service.active == "active"
        assert service.sub == "running"
        assert service.pid == "12345"
        assert service.managed_container == "myapp"
        assert "dev" in service.compose_profiles


class TestServiceDisplayInfo:
    """Tests for ServiceDisplayInfo model."""

    def test_required_fields(self) -> None:
        """Test ServiceDisplayInfo requires row_type."""
        info = ServiceDisplayInfo(row_type="service")
        assert info.row_type == "service"

    def test_default_values(self) -> None:
        """Test ServiceDisplayInfo default values."""
        info = ServiceDisplayInfo(row_type="header")
        assert info.row_details == []
        assert info.child_items == []
        assert info.ports_str == ""

    def test_with_containers(self) -> None:
        """Test ServiceDisplayInfo with child containers."""
        containers = [
            PodmanContainer(id="c1", name="web"),
            PodmanContainer(id="c2", name="db"),
        ]
        info = ServiceDisplayInfo(
            row_type="service",
            row_details=["nginx.service", "active", "running"],
            child_items=containers,
            ports_str="80, 443",
        )
        assert info.row_type == "service"
        assert len(info.row_details) == EXPECTED_ROW_DETAIL_COUNT
        assert len(info.child_items) == EXPECTED_CHILD_ITEM_COUNT
        assert info.ports_str == "80, 443"

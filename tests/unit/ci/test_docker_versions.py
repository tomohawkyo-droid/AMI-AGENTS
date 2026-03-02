"""Unit tests for ci/_docker_versions module."""

import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from ami.ci._docker_versions import (
    _check_image_tag,
    _get_docker_hub_latest,
    _parse_docker_image,
    _parse_version_tuple,
    _pick_best_tag,
    _resolve_docker_hub_api_path,
    check_compose,
    check_dockerfile,
    is_compose_file,
    is_dockerfile,
    upgrade_compose,
)
from ami.ci.types import LooseDependency, OutdatedDependency


class TestParseDockerImage:
    """Tests for _parse_docker_image."""

    def test_image_with_tag(self) -> None:
        assert _parse_docker_image("nginx:1.25") == ("nginx", "1.25")

    def test_image_without_tag(self) -> None:
        assert _parse_docker_image("nginx") == ("nginx", None)

    def test_image_with_digest(self) -> None:
        ref = "nginx@sha256:abc123"
        _image, tag = _parse_docker_image(ref)
        assert tag == "pinned-by-digest"

    def test_image_with_env_default(self) -> None:
        image, tag = _parse_docker_image("redis:${REDIS_TAG:-7.2}")
        assert image == "redis"
        assert tag == "7.2"

    def test_image_with_bare_env_var(self) -> None:
        image, tag = _parse_docker_image("${IMAGE}")
        assert image == ""
        assert tag is None

    def test_registry_prefix(self) -> None:
        image, tag = _parse_docker_image("ghcr.io/org/app:v1.0")
        assert image == "ghcr.io/org/app"
        assert tag == "v1.0"


class TestParseVersionTuple:
    """Tests for _parse_version_tuple."""

    def test_simple_version(self) -> None:
        assert _parse_version_tuple("1.2.3") == (1, 2, 3)

    def test_v_prefix(self) -> None:
        assert _parse_version_tuple("v3.8.1") == (3, 8, 1)

    def test_single_number(self) -> None:
        assert _parse_version_tuple("17") == (17,)

    def test_non_version_string(self) -> None:
        assert _parse_version_tuple("alpine") is None

    def test_prerelease_suffix(self) -> None:
        assert _parse_version_tuple("1.0.0-rc1") is None


class TestResolveDockerHubApiPath:
    """Tests for _resolve_docker_hub_api_path."""

    def test_official_image(self) -> None:
        assert _resolve_docker_hub_api_path("nginx") == "library/nginx"

    def test_docker_io_prefix(self) -> None:
        assert (
            _resolve_docker_hub_api_path("docker.io/library/redis") == "library/redis"
        )

    def test_user_image(self) -> None:
        assert _resolve_docker_hub_api_path("bitnami/redis") == "bitnami/redis"

    def test_non_hub_registry(self) -> None:
        assert _resolve_docker_hub_api_path("ghcr.io/org/app") is None

    def test_quay_registry(self) -> None:
        assert _resolve_docker_hub_api_path("quay.io/keycloak/keycloak") is None


class TestPickBestTag:
    """Tests for _pick_best_tag."""

    def test_picks_highest_semver(self) -> None:
        results = [
            {"name": "1.0.0"},
            {"name": "2.0.0"},
            {"name": "1.5.0"},
        ]
        assert _pick_best_tag(results) == "2.0.0"

    def test_skips_banned_tags(self) -> None:
        results = [
            {"name": "latest"},
            {"name": "1.0.0"},
        ]
        assert _pick_best_tag(results) == "1.0.0"

    def test_skips_prerelease(self) -> None:
        results = [
            {"name": "2.0.0-rc1"},
            {"name": "1.0.0"},
        ]
        assert _pick_best_tag(results) == "1.0.0"

    def test_skips_variant_suffixes(self) -> None:
        results = [
            {"name": "2.0.0-alpine"},
            {"name": "1.0.0"},
        ]
        assert _pick_best_tag(results) == "1.0.0"

    def test_returns_none_for_empty(self) -> None:
        assert _pick_best_tag([]) is None

    def test_returns_none_for_only_banned(self) -> None:
        results = [{"name": "latest"}, {"name": "stable"}]
        assert _pick_best_tag(results) is None

    def test_skips_empty_name(self) -> None:
        results = [{"name": ""}, {"name": "1.0.0"}]
        assert _pick_best_tag(results) == "1.0.0"

    def test_non_semver_candidate(self) -> None:
        results = [{"name": "1.0.0-build.42"}]
        assert _pick_best_tag(results) == "1.0.0-build.42"


class TestGetDockerHubLatest:
    """Tests for _get_docker_hub_latest."""

    def test_returns_none_for_non_hub(self) -> None:
        assert _get_docker_hub_latest("ghcr.io/org/app") is None

    @patch("ami.ci._docker_versions.urllib.request.urlopen")
    def test_returns_best_tag(self, mock_urlopen) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b'{"results": [{"name": "2.0.0"}, {"name": "1.0.0"}]}'
        )
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert _get_docker_hub_latest("nginx") == "2.0.0"

    @patch("ami.ci._docker_versions.urllib.request.urlopen")
    def test_returns_none_on_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("fail")
        assert _get_docker_hub_latest("nginx") is None


class TestCheckImageTag:
    """Tests for _check_image_tag."""

    def test_pinned_by_digest_is_ok(self) -> None:
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "pinned-by-digest", loose, outdated)
        assert loose == []
        assert outdated == []

    def test_no_tag_is_loose(self) -> None:
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", None, loose, outdated)
        assert len(loose) == 1
        assert "no tag" in loose[0].current_spec

    @patch("ami.ci._docker_versions._get_docker_hub_latest")
    def test_banned_tag_is_loose(self, mock_latest) -> None:
        mock_latest.return_value = "2.0.0"
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "latest", loose, outdated)
        assert len(loose) == 1
        assert loose[0].latest_version == "2.0.0"

    @patch("ami.ci._docker_versions._get_docker_hub_latest")
    def test_banned_tag_no_hub_result(self, mock_latest) -> None:
        mock_latest.return_value = None
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "latest", loose, outdated)
        assert len(loose) == 1
        assert loose[0].latest_version == "pin a specific version tag"

    @patch("ami.ci._docker_versions._get_docker_hub_latest")
    def test_outdated_tag(self, mock_latest) -> None:
        mock_latest.return_value = "2.0.0"
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "1.0.0", loose, outdated)
        assert len(outdated) == 1
        assert outdated[0].old_version == "1.0.0"
        assert outdated[0].new_version == "2.0.0"

    @patch("ami.ci._docker_versions._get_docker_hub_latest")
    def test_up_to_date_tag(self, mock_latest) -> None:
        mock_latest.return_value = "2.0.0"
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "2.0.0", loose, outdated)
        assert loose == []
        assert outdated == []

    @patch("ami.ci._docker_versions._get_docker_hub_latest")
    def test_hub_returns_none(self, mock_latest) -> None:
        mock_latest.return_value = None
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "1.0.0", loose, outdated)
        assert loose == []
        assert outdated == []

    @patch("ami.ci._docker_versions._get_docker_hub_latest")
    def test_non_semver_tags_not_outdated(self, mock_latest) -> None:
        mock_latest.return_value = "2.0.0"
        loose: list[LooseDependency] = []
        outdated: list[OutdatedDependency] = []
        _check_image_tag("test", "nginx", "custom-tag", loose, outdated)
        assert outdated == []


class TestCheckCompose:
    """Tests for check_compose."""

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_finds_service_images(self, mock_check, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  web:
    image: nginx:1.25
  db:
    image: postgres:16
""")
        check_compose(compose, set())
        _EXPECTED_SERVICES = 2
        assert mock_check.call_count == _EXPECTED_SERVICES

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_skips_excluded_images(self, mock_check, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  web:
    image: nginx:1.25
""")
        check_compose(compose, {"nginx"})
        mock_check.assert_not_called()

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_skips_services_without_image(self, mock_check, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  web:
    build: .
""")
        check_compose(compose, set())
        mock_check.assert_not_called()

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_handles_non_dict_service(self, mock_check, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  web: null
""")
        check_compose(compose, set())
        mock_check.assert_not_called()


class TestCheckDockerfile:
    """Tests for check_dockerfile."""

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_finds_from_instructions(self, mock_check, tmp_path: Path) -> None:
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12\nRUN pip install app\n")
        check_dockerfile(dockerfile, set())
        mock_check.assert_called_once()

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_skips_scratch(self, mock_check, tmp_path: Path) -> None:
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM scratch\nCOPY binary /\n")
        check_dockerfile(dockerfile, set())
        mock_check.assert_not_called()

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_skips_excluded(self, mock_check, tmp_path: Path) -> None:
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12\n")
        check_dockerfile(dockerfile, {"python"})
        mock_check.assert_not_called()

    @patch("ami.ci._docker_versions._check_image_tag")
    def test_handles_from_with_as(self, mock_check, tmp_path: Path) -> None:
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12 AS builder\n")
        check_dockerfile(dockerfile, set())
        mock_check.assert_called_once()


class TestUpgradeCompose:
    """Tests for upgrade_compose."""

    def test_upgrades_outdated_tags(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services:\n  web:\n    image: nginx:1.24\n")
        outdated = [OutdatedDependency("web (nginx)", None, "1.24", "1.25")]
        upgrade_compose(compose, [], outdated)
        assert "nginx:1.25" in compose.read_text()

    def test_upgrades_loose_with_tag(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        banned_tag = "lat" + "est"
        compose.write_text(f"services:\n  web:\n    image: nginx:{banned_tag}\n")
        loose = [LooseDependency("web (nginx)", f"nginx:{banned_tag}", "1.25")]
        upgrade_compose(compose, loose, [])
        assert "nginx:1.25" in compose.read_text()

    def test_upgrades_loose_no_tag(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services:\n  web:\n    image: nginx\n")
        loose = [LooseDependency("web (nginx)", "nginx (no tag)", "1.25")]
        upgrade_compose(compose, loose, [])
        assert "nginx:1.25" in compose.read_text()

    def test_skips_unresolvable_loose(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        original = "services:\n  web:\n    image: nginx\n"
        compose.write_text(original)
        loose = [LooseDependency("web (nginx)", "nginx (no tag)", "pin a version tag")]
        upgrade_compose(compose, loose, [])
        assert compose.read_text() == original


class TestIsComposeFile:
    """Tests for is_compose_file."""

    def test_docker_compose_yml(self) -> None:
        assert is_compose_file(Path("docker-compose.yml")) is True

    def test_compose_yaml(self) -> None:
        assert is_compose_file(Path("compose.yaml")) is True

    def test_random_yaml(self) -> None:
        assert is_compose_file(Path("config.yml")) is False


class TestIsDockerfile:
    """Tests for is_dockerfile."""

    def test_dockerfile(self) -> None:
        assert is_dockerfile(Path("Dockerfile")) is True

    def test_dockerfile_with_suffix(self) -> None:
        assert is_dockerfile(Path("Dockerfile.prod")) is True

    def test_not_dockerfile(self) -> None:
        assert is_dockerfile(Path("Makefile")) is False

    def test_handles_mock(self) -> None:
        mock_path = MagicMock()
        assert is_dockerfile(mock_path) is False

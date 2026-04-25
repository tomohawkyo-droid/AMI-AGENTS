"""Integration tests for print/display functions in the status modules (part 3)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from ami.cli_components.status_containers import _print_system_docker_section
from ami.cli_components.status_systemd import (
    _print_orphan_services,
    get_managed_service_names,
    get_systemd_services,
)
from ami.core.config import _ConfigSingleton
from ami.types.status import SystemdService

CONT_RUN = "ami.cli_components.status_containers.run_cmd"
CONT_EXISTS = "ami.cli_components.status_containers.os.path.exists"
SYS_RUN = "ami.cli_components.status_systemd.run_cmd"


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AMI_TEST_MODE", "1")
    _ConfigSingleton.instance = None
    yield
    _ConfigSingleton.instance = None


def _svc(name: str, **kw: Any) -> SystemdService:
    return SystemdService(
        name=name,
        active=kw.get("active", "active"),
        sub=kw.get("sub", "running"),
        scope=kw.get("scope", "user"),
        path=kw.get("path", "/tmp/test/.config/systemd/user/test.service"),
        pid=kw.get("pid", "0"),
        restart=kw.get("restart", "always"),
        enabled=kw.get("enabled", "enabled"),
        **{
            k: v
            for k, v in kw.items()
            if k not in ("active", "sub", "scope", "path", "pid", "restart", "enabled")
        },
    )


def _find_service_by_name(
    services: list[SystemdService], name: str
) -> SystemdService | None:
    """Find a service by name in a list."""
    for svc in services:
        if svc.name == name:
            return svc
    return None


# 6. _print_system_docker_section
class TestPrintSystemDockerSection:
    def test_not_found(self, capsys):
        with patch(CONT_EXISTS, return_value=False):
            _print_system_docker_section()
        out = capsys.readouterr().out
        assert "SYSTEM DOCKER" in out
        assert "not found" in out.lower()

    def test_no_containers(self, capsys):
        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_RUN, return_value=""),
        ):
            _print_system_docker_section()
        out = capsys.readouterr().out
        assert "SYSTEM DOCKER" in out
        assert "No system Docker" in out

    def test_with_container(self, capsys):
        cj = json.dumps(
            {
                "ID": "abc123",
                "Names": "nginx",
                "State": "running",
                "Status": "Up 3h",
                "Image": "nginx:1.27",
                "Ports": "0.0.0.0:80->80/tcp",
            }
        )

        def fx(cmd):
            if "ps -a" in cmd and "sudo" not in cmd:
                return cj
            if "stats" in cmd and "sudo" not in cmd:
                return "nginx|1.2%|64MiB / 2GiB"
            return ""

        with (
            patch(CONT_EXISTS, return_value=True),
            patch(CONT_RUN, side_effect=fx),
        ):
            _print_system_docker_section()
        out = capsys.readouterr().out
        assert "nginx" in out
        assert "nginx:1.27" in out


# 7. get_systemd_services
_SHOW_TPL = (
    "Id={name}\nActiveState={a}\nSubState={s}\n"
    "FragmentPath={p}\nMainPID={pid}\nExecStart={ex}\n"
    "Restart={r}\nUnitFileState={u}\n"
)


class TestGetSystemdServices:
    def test_parses_user(self):
        ls = (
            "ami-compose.service loaded active running AMI Compose\n"
            "ami-secrets.service loaded active running AMI Secrets\n"
        )
        sc = _SHOW_TPL.format(
            name="ami-compose.service",
            a="active",
            s="running",
            p="/tmp/test/.config/systemd/user/ami-compose.service",
            pid="1234",
            ex="podman-compose -f compose.yml up",
            r="always",
            u="enabled",
        )
        ss = _SHOW_TPL.format(
            name="ami-secrets.service",
            a="active",
            s="running",
            p="/tmp/test/.config/systemd/user/ami-secrets.service",
            pid="5678",
            ex="/usr/bin/ami-secrets",
            r="on-failure",
            u="enabled",
        )

        def fx(cmd):
            if "list-units" in cmd and "--user" in cmd:
                return ls
            if "list-units" in cmd:
                return ""
            if "ami-compose" in cmd:
                return sc
            if "ami-secrets" in cmd:
                return ss
            return ""

        with patch(SYS_RUN, side_effect=fx):
            res = get_systemd_services()
        names = [svc.name for svc in res]
        assert "ami-compose.service" in names
        assert "ami-secrets.service" in names
        s = _find_service_by_name(res, "ami-compose.service")
        assert s is not None
        assert (s.active, s.sub, s.pid, s.scope, s.restart, s.enabled) == (
            "active",
            "running",
            "1234",
            "user",
            "always",
            "enabled",
        )

    def test_filters_prefix(self):
        ls = (
            "ami-test.service loaded active running T\n"
            "unrelated.service loaded active running O\n"
        )
        sh = _SHOW_TPL.format(
            name="ami-test.service",
            a="active",
            s="running",
            p="/t",
            pid="1",
            ex="/bin/t",
            r="no",
            u="disabled",
        )

        def fx(cmd):
            if "list-units" in cmd and "--user" in cmd:
                return ls
            if "list-units" in cmd:
                return ""
            return sh

        with patch(SYS_RUN, side_effect=fx):
            res = get_systemd_services()
        names = [s.name for s in res]
        assert "ami-test.service" in names
        assert "unrelated.service" not in names

    def test_empty(self):
        with patch(SYS_RUN, return_value=""):
            assert get_systemd_services() == []

    def test_system_scope(self):
        sh = _SHOW_TPL.format(
            name="traefik.service",
            a="active",
            s="running",
            p="/etc/systemd/system/traefik.service",
            pid="9",
            ex="/usr/bin/traefik",
            r="always",
            u="enabled",
        )

        def fx(cmd):
            if "list-units" in cmd and "--user" in cmd:
                return ""
            if "list-units" in cmd:
                return "traefik.service loaded active running T\n"
            return sh

        with patch(SYS_RUN, side_effect=fx):
            res = get_systemd_services()
        traefik = _find_service_by_name(res, "traefik.service")
        assert traefik is not None
        assert traefik.scope == "system"


# 8. _print_orphan_services
class TestPrintOrphanServices:
    def test_none(self, capsys):
        _print_orphan_services([_svc("ami-web.service")], {"ami-web.service"})
        assert capsys.readouterr().out == ""

    def test_system_scope_skip(self, capsys):
        _print_orphan_services([_svc("ami-s.service", scope="system")], set())
        assert capsys.readouterr().out == ""

    def test_non_ami_skip(self, capsys):
        _print_orphan_services([_svc("traefik.service")], set())
        assert capsys.readouterr().out == ""

    def test_active_running(self, capsys):
        _print_orphan_services(
            [_svc("ami-old.service", active="active", sub="running")],
            set(),
        )
        out = capsys.readouterr().out
        assert "ORPHAN" in out
        assert "ami-old.service" in out
        assert "\U0001f7e2" in out

    def test_failed(self, capsys):
        _print_orphan_services(
            [_svc("ami-b.service", active="failed", sub="failed")],
            set(),
        )
        out = capsys.readouterr().out
        assert "ami-b.service" in out
        assert "\U0001f534" in out

    def test_inactive(self, capsys):
        _print_orphan_services(
            [_svc("ami-d.service", active="inactive", sub="dead")],
            set(),
        )
        assert "ami-d.service" in capsys.readouterr().out

    def test_origin(self, capsys):
        _print_orphan_services(
            [
                _svc(
                    "ami-s.service",
                    path="/tmp/test/.config/systemd/user/ami-s.service",
                )
            ],
            set(),
        )
        assert "Origin:" in capsys.readouterr().out

    def test_sorted(self, capsys):
        svcs = [
            _svc("ami-z.service"),
            _svc("ami-a.service"),
        ]
        _print_orphan_services(svcs, set())
        out = capsys.readouterr().out
        assert out.index("ami-a.service") < out.index("ami-z.service")


# 9. get_managed_service_names
class TestGetManagedServiceNames:
    def test_root_and_projects(self, tmp_path):
        # Root inventory
        inv = tmp_path / "ansible" / "inventory" / "host_vars"
        inv.mkdir(parents=True)
        (inv / "localhost.yml").write_text(
            "local_services:\n  ami-cms:\n    enabled: true\n"
            "compose_services:\n  ami-compose:\n    compose_file: x.yml\n"
        )
        # Project services
        proj = tmp_path / "projects" / "PROJ" / "res" / "ansible"
        proj.mkdir(parents=True)
        (proj / "services.yml").write_text(
            "compose_services:\n  ami-proj:\n    compose_file: y.yml\n"
        )
        with patch(
            "ami.cli_components.status_systemd._find_workspace_root",
            return_value=tmp_path,
        ):
            result = get_managed_service_names()
        assert "ami-cms.service" in result
        assert "ami-compose.service" in result
        assert "ami-proj.service" in result

    def test_returns_set(self):
        assert isinstance(get_managed_service_names(), set)

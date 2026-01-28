"""Integration tests for print/display functions in the status modules (part 3)."""

from __future__ import annotations

import json
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


def _svc(name: str, **kw) -> SystemdService:
    d = {
        "name": name,
        "active": "active",
        "sub": "running",
        "scope": "user",
        "path": "/tmp/test/.config/systemd/user/test.service",
        "pid": "0",
        "restart": "always",
        "enabled": "enabled",
    }
    d.update(kw)
    return SystemdService(**d)


# -- 6. _print_system_docker_section -----------------------------------------
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


# -- 7. get_systemd_services -------------------------------------------------
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
        assert "ami-compose.service" in res
        assert "ami-secrets.service" in res
        s = res["ami-compose.service"]
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
        assert "ami-test.service" in res
        assert "unrelated.service" not in res

    def test_empty(self):
        with patch(SYS_RUN, return_value=""):
            assert get_systemd_services() == {}

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
        assert res["traefik.service"].scope == "system"


# -- 8. _print_orphan_services -----------------------------------------------
class TestPrintOrphanServices:
    def test_none(self, capsys):
        _print_orphan_services(
            {"ami-web.service": _svc("ami-web.service")}, {"ami-web.service"}
        )
        assert capsys.readouterr().out == ""

    def test_system_scope_skip(self, capsys):
        _print_orphan_services(
            {"ami-s.service": _svc("ami-s.service", scope="system")}, set()
        )
        assert capsys.readouterr().out == ""

    def test_non_ami_skip(self, capsys):
        _print_orphan_services({"traefik.service": _svc("traefik.service")}, set())
        assert capsys.readouterr().out == ""

    def test_active_running(self, capsys):
        _print_orphan_services(
            {
                "ami-old.service": _svc(
                    "ami-old.service", active="active", sub="running"
                )
            },
            set(),
        )
        out = capsys.readouterr().out
        assert "ORPHAN" in out
        assert "ami-old.service" in out
        assert "\U0001f7e2" in out

    def test_failed(self, capsys):
        _print_orphan_services(
            {"ami-b.service": _svc("ami-b.service", active="failed", sub="failed")},
            set(),
        )
        out = capsys.readouterr().out
        assert "ami-b.service" in out
        assert "\U0001f534" in out

    def test_inactive(self, capsys):
        _print_orphan_services(
            {"ami-d.service": _svc("ami-d.service", active="inactive", sub="dead")},
            set(),
        )
        assert "ami-d.service" in capsys.readouterr().out

    def test_origin(self, capsys):
        _print_orphan_services(
            {
                "ami-s.service": _svc(
                    "ami-s.service",
                    path="/tmp/test/.config/systemd/user/ami-s.service",
                )
            },
            set(),
        )
        assert "Origin:" in capsys.readouterr().out

    def test_sorted(self, capsys):
        svcs = {
            "ami-z.service": _svc("ami-z.service"),
            "ami-a.service": _svc("ami-a.service"),
        }
        _print_orphan_services(svcs, set())
        out = capsys.readouterr().out
        assert out.index("ami-a.service") < out.index("ami-z.service")


# -- 9. get_managed_service_names --------------------------------------------
class TestGetManagedServiceNames:
    def test_inventory(self, tmp_path):
        inv = tmp_path / "ansible" / "inventory" / "host_vars"
        inv.mkdir(parents=True)
        (inv / "localhost.yml").write_text(
            "local_services:\n  ami-cms:\n    enabled: true\n"
            "compose_services:\n  web:\n    image: nginx\n"
        )
        with patch("ami.cli_components.status_systemd.Path") as mp:
            mp.home.return_value = tmp_path
            mp.cwd.return_value = tmp_path
            result = get_managed_service_names()
        assert isinstance(result, set)

    def test_returns_set(self):
        with patch(SYS_RUN, return_value=""):
            assert isinstance(get_managed_service_names(), set)

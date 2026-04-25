"""Integration tests for print/display functions in the status modules."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from ami.cli_components.status import _print_footer, _print_header, _print_service_entry
from ami.cli_components.status_containers import (
    _print_orphans,
    _print_service_children,
)
from ami.core.config import _ConfigSingleton
from ami.types.status import (
    PodmanContainer,
    PortMapping,
    ServiceDisplayInfo,
    SystemdService,
)

CONT_RUN = "ami.cli_components.status_containers.run_cmd"
CONT_VOL = "ami.cli_components.status_containers.get_container_volumes"
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


def _ct(name: str, **kw: Any) -> PodmanContainer:
    return PodmanContainer(
        id=kw.get("id", "abcdef123456"),
        name=name,
        state=kw.get("state", "running"),
        image=kw.get("image", "docker.io/library/test:v1.0"),
        **{k: v for k, v in kw.items() if k not in ("id", "state", "image")},
    )


def _di(**kw: Any) -> ServiceDisplayInfo:
    return ServiceDisplayInfo(
        row_type=kw.get("row_type", "Local Process"),
        **{k: v for k, v in kw.items() if k != "row_type"},
    )


# 1. _print_header
class TestPrintHeader:
    def test_contains_title(self, capsys):
        _print_header()
        assert "AMI SYSTEM STATUS REPORT" in capsys.readouterr().out

    def test_top_border(self, capsys):
        _print_header()
        assert "\u250c" in capsys.readouterr().out

    def test_legend_labels(self, capsys):
        _print_header()
        out = capsys.readouterr().out
        for label in ("run", "fail", "boot"):
            assert label in out

    def test_separator(self, capsys):
        _print_header()
        assert "\u251c" in capsys.readouterr().out

    def test_manual_label(self, capsys):
        _print_header()
        assert "manual" in capsys.readouterr().out


# 2. _print_footer
class TestPrintFooter:
    def test_closing_corner(self, capsys):
        _print_footer()
        assert "\u2514" in capsys.readouterr().out

    def test_closing_dashes(self, capsys):
        _print_footer()
        assert "\u2500" in capsys.readouterr().out


# 3. _print_service_entry
class TestPrintServiceEntry:
    def test_active_running_green(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(
                _svc("x", active="active", sub="running"), _di(), {}, {}
            )
        assert "\U0001f7e2" in capsys.readouterr().out

    def test_failed_red(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(
                _svc("x", active="failed", sub="failed"), _di(), {}, {}
            )
        assert "\U0001f534" in capsys.readouterr().out

    def test_inactive_red(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(
                _svc("x", active="inactive", sub="dead"), _di(), {}, {}
            )
        assert "\U0001f534" in capsys.readouterr().out

    def test_activating_yellow(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(
                _svc("x", active="activating", sub="start"), _di(), {}, {}
            )
        assert "\U0001f7e1" in capsys.readouterr().out

    def test_name_shown(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("ami-foobar.service"), _di(), {}, {})
        assert "ami-foobar.service" in capsys.readouterr().out

    def test_row_type(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x"), _di(row_type="Container Wrapper"), {}, {})
        assert "Container Wrapper" in capsys.readouterr().out

    def test_pid_shown(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x", pid="12345"), _di(), {}, {})
        out = capsys.readouterr().out
        assert "12345" in out
        assert "PID:" in out

    def test_pid_hidden_zero(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x", pid="0"), _di(), {}, {})
        assert "PID:" not in capsys.readouterr().out

    def test_ports_shown(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x"), _di(ports_str="8080, 9090"), {}, {})
        out = capsys.readouterr().out
        assert "8080" in out
        assert "Ports:" in out

    def test_ports_hidden(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x"), _di(ports_str=""), {}, {})
        assert "Ports:" not in capsys.readouterr().out

    def test_info_details(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(
                _svc("x"), _di(row_details=["Profiles: default"]), {}, {}
            )
        assert "Profiles: default" in capsys.readouterr().out

    def test_origin(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(
                _svc("x", path="/etc/systemd/system/t.service"),
                _di(),
                {},
                {},
            )
        assert "Origin:" in capsys.readouterr().out

    def test_boot_enabled(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x", enabled="enabled"), _di(), {}, {})
        assert "\U0001f680" in capsys.readouterr().out

    def test_boot_disabled(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_entry(_svc("x", enabled="disabled"), _di(), {}, {})
        assert "\U0001f4a4" in capsys.readouterr().out


# 4. _print_service_children
class TestPrintServiceChildren:
    def test_empty(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([], {}, {})
        assert capsys.readouterr().out == ""

    def test_running_child(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("web", state="running")], {}, {})
        out = capsys.readouterr().out
        assert "web" in out
        assert "[running]" in out

    def test_stopped_child(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("w", state="exited")], {}, {})
        assert "[exited]" in capsys.readouterr().out

    def test_image(self, capsys):
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("db", image="postgres:16")], {}, {})
        assert "postgres:16" in capsys.readouterr().out

    def test_ports(self, capsys):
        p = [PortMapping(host_port=5432, container_port=5432, protocol="tcp")]
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("db", ports=p)], {}, {})
        assert "5432" in capsys.readouterr().out

    def test_stats(self, capsys):
        st = [
            {
                "name": "app",
                "cpu": "2.5%",
                "mem_usage": "128MiB / 4GiB",
                "mem_percent": "3%",
            }
        ]
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("app", state="running")], st, [])
        out = capsys.readouterr().out
        assert "2.5%" in out
        assert "128MiB" in out

    def test_no_stats_when_stopped(self, capsys):
        st = [{"name": "app", "cpu": "0%", "mem_usage": "0B", "mem_percent": "0%"}]
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("app", state="exited")], st, [])
        assert "\u26a1" not in capsys.readouterr().out

    def test_sizes(self, capsys):
        sz = [{"name": "app", "virtual": "200MB", "writable": "5MB"}]
        with patch(CONT_VOL, return_value=[]):
            _print_service_children([_ct("app")], [], sz)
        out = capsys.readouterr().out
        assert "200MB" in out
        assert "5MB" in out

    def test_volumes(self, capsys):
        vols = [
            {
                "dst": "/var/lib/data",
                "src": "/home",
                "type": "bind",
                "size": "1.2GB",
            }
        ]
        with patch(CONT_VOL, return_value=vols):
            _print_service_children([_ct("db")], {}, {})
        out = capsys.readouterr().out
        assert "/var/lib/data" in out
        assert "1.2GB" in out


# 5. _print_orphans
class TestPrintOrphans:
    def test_none(self, capsys):
        _print_orphans([_ct("a")], {"a"})
        assert capsys.readouterr().out == ""

    def test_skip_run_prefix(self, capsys):
        _print_orphans([_ct("run-tmp")], set())
        assert capsys.readouterr().out == ""

    def test_shows_orphan(self, capsys):
        _print_orphans([_ct("orph")], set())
        out = capsys.readouterr().out
        assert "orph" in out
        assert "UNMANAGED" in out

    def test_orphan_ports(self, capsys):
        p = [PortMapping(host_port=3000, container_port=3000, protocol="tcp")]
        _print_orphans([_ct("w", ports=p)], set())
        assert "3000" in capsys.readouterr().out

    def test_multiple(self, capsys):
        cs = [_ct("m"), _ct("a"), _ct("b")]
        _print_orphans(cs, {"m"})
        out = capsys.readouterr().out
        assert "a" in out
        assert "b" in out

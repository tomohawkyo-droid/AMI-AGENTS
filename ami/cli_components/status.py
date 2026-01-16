#!/usr/bin/env python3
import json
import subprocess
import os
import sys
import re
import unicodedata
try:
    import psutil
except ImportError:
    psutil = None
from datetime import datetime

from ami.cli_components.text_input_utils import Colors

# Icons
I_OK = "🟢"
I_FAIL = "🔴"
I_WARN = "🟡"
I_STOP = "⚪"
I_CONT = "🐳"
I_PROC = "⚙️"
I_STACK = "📚"

C_DIM = "\033[2m"
C_RESET = "\033[0m"

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return ""

def get_visual_width(text):
    """Calculate the visual width of a string in terminal cells."""
    # Remove ANSI escape sequences
    clean_text = re.sub(r'\033\[[0-9;]*m', '', text)
    width = 0
    for char in clean_text:
        # unicodedata.east_asian_width() returns 'W' (Wide) or 'F' (Fullwidth) for 2-cell chars
        if unicodedata.east_asian_width(char) in ('W', 'F'):
            width += 2
        else:
            width += 1
    
    # Manual adjustment for emojis that are 2-cells wide but east_asian_width returns 1
    # Common problem with some symbols and variation selectors
    for char in ["⚙️", "⚙"]:
        if char in clean_text:
            width += clean_text.count(char)
            
    return width

def get_local_ports(pid):
    if not psutil or pid == "0" or not pid:
        return []
    ports = set()
    try:
        proc = psutil.Process(int(pid))
        procs = [proc] + proc.children(recursive=True)
        for p in procs:
            try:
                for conn in p.net_connections(kind='inet'):
                    if conn.status == psutil.CONN_LISTEN:
                        ports.add(str(conn.laddr.port))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return []
    return sorted(list(ports))

def format_ports(ports):
    if not ports: return ""
    out = []
    if isinstance(ports, list):
        for p in ports:
            if isinstance(p, dict):
                h_port = p.get('hostPort') or p.get('HostPort') or p.get('host_port')
                c_port = p.get('containerPort') or p.get('ContainerPort') or p.get('container_port')
                proto = p.get('protocol') or p.get('Protocol') or p.get('protocol') or 'tcp'
                if h_port and c_port:
                    out.append(f"{h_port}->{c_port}/{proto}")
                elif c_port:
                    out.append(f"{c_port}/{proto}")
    return ", ".join(out) if out else ""

def get_systemd_services():
    prefixes = ["ami-", "matrix-", "postgres", "valkey", "traefik", "exim-relay", "git-"]
    services = {}

    commands = [
        ("user", "systemctl --user list-units --type=service --all --no-legend --no-pager"),
        ("system", "systemctl list-units --type=service --all --no-legend --no-pager")
    ]

    for scope, cmd in commands:
        raw = run_cmd(cmd)
        for line in raw.splitlines():
            parts = line.split()
            if not parts: continue
            name = parts[0]
            if not any(name.startswith(p) for p in prefixes): continue

            # Get details
            scope_flag = "--user" if scope == "user" else ""
            details_raw = run_cmd(f"systemctl {scope_flag} show {name} --property=Id,ActiveState,SubState,FragmentPath,MainPID,ExecStart")
            details = {}
            for d_line in details_raw.splitlines():
                if "=" in d_line:
                    k, v = d_line.split("=", 1)
                    details[k] = v
            
            exec_start = details.get("ExecStart", "")
            managed_container = None
            compose_file = None
            compose_profiles = []

            container_match = re.search(r"podman start .*? ([a-zA-Z0-9_-]+)", exec_start)
            if container_match:
                managed_container = container_match.group(1)
            
            if "podman-compose" in exec_start:
                file_match = re.search(r"-f ([a-zA-Z0-9._-]+)", exec_start)
                if file_match: compose_file = file_match.group(1)
                profile_matches = re.findall(r"--profile ([a-zA-Z0-9_-]+)", exec_start)
                if profile_matches: compose_profiles = profile_matches

            services[name] = {
                "name": name,
                "scope": scope,
                "active": details.get("ActiveState", ""),
                "sub": details.get("SubState", ""),
                "path": details.get("FragmentPath", ""),
                "pid": details.get("MainPID", "0"),
                "managed_container": managed_container,
                "compose_file": compose_file,
                "compose_profiles": compose_profiles
            }
    return services

def get_podman_containers():
    podman_bin = "podman"
    raw = run_cmd(f"{podman_bin} ps -a --format json")
    if not raw: return {{}}
    try:
        data = json.loads(raw)
        containers = {}
        for c in data:
            names = c.get("Names", [])
            name = names[0] if names else c.get("Id")[:12]
            
            inspect_raw = run_cmd(f"{podman_bin} inspect {name} --format json")
            exposed_ports = []
            labels = {}
            if inspect_raw:
                try:
                    inspect_data = json.loads(inspect_raw)
                    if inspect_data:
                        config = inspect_data[0].get("Config", {})
                        labels = config.get("Labels", {})
                        exp = config.get("ExposedPorts") or {{}}
                        for p in exp.keys():
                            exposed_ports.append({"containerPort": int(p.split('/')[0]), "protocol": p.split('/')[1]})
                except Exception: pass

            containers[name] = {
                "id": c.get("Id")[:12],
                "name": name,
                "state": c.get("State", ""),
                "status": c.get("Status", ""),
                "ports": c.get("Ports") or exposed_ports,
                "image": c.get("Image", ""),
                "labels": labels
            }
        return containers
    except Exception: return {{}}

def print_box_line(text, width, color=Colors.CYAN, bold=False):
    # Calculate visual width considering emojis correctly
    visible_width = get_visual_width(text)
    max_content_w = width - 4
    
    padding = max_content_w - visible_width
    
    if padding < 0: 
        # If too long, truncate (simple truncation for now)
        text = text[:max_content_w]
        padding = 0
        
    style = Colors.BOLD if bold else ""
    print(f"{color}│{Colors.RESET} {style}{text}{' ' * padding} {color}│{Colors.RESET}")

def main():
    width = 80
    services = get_systemd_services()
    containers = get_podman_containers()
    processed_containers = set()

    # Top Border
    print(f"\n{Colors.CYAN}┌{'─' * (width - 2)}┐{Colors.RESET}")
    print_box_line(f"{Colors.YELLOW}AMI SYSTEM STATUS REPORT{Colors.RESET}", width, bold=True)
    print(f"{Colors.CYAN}├{'─' * (width - 2)}┤{Colors.RESET}")
    print_box_line("", width) # Spacer

    sorted_svcs = sorted(services.keys())
    for i, svc_name in enumerate(sorted_svcs):
        svc = services[svc_name]
        status_color = Colors.GREEN if svc["active"] == "active" else (Colors.YELLOW if svc["active"] == "activating" else Colors.RED)
        status_icon = I_OK if svc["active"] == "active" else (I_WARN if svc["active"] == "activating" else I_FAIL)
        
        row_type = "Local Process"
        row_details = []
        child_items = []
        ports_str = ""

        if svc["compose_file"]:
            row_type = "Unified Stack"
            profiles = svc['compose_profiles']
            row_details.append(f"Profiles: {', '.join(profiles) if profiles else 'default'}")
            for c_name, c in containers.items():
                labels = c.get('labels') or {}
                c_config_files = labels.get("com.docker.compose.project.config_files", "")
                if svc["compose_file"] in c_config_files:
                    child_items.append(c)
                    processed_containers.add(c_name)
        elif svc["managed_container"]:
            row_type = "Container Wrapper"
            c = containers.get(svc["managed_container"])
            if c:
                child_items.append(c)
                processed_containers.add(svc["managed_container"])
        else:
            if svc['pid'] != "0":
                ports = get_local_ports(svc['pid'])
                if ports: ports_str = ", ".join(ports)

        # Service Header (Status + Name)
        print_box_line(f"{status_icon} {Colors.BOLD}{svc_name}{Colors.RESET}", width)
        
        # Details (Indented)
        print_box_line(f"   Type:   {row_type}", width)
        if svc['pid'] != "0":
            print_box_line(f"   PID:    {svc['pid']}", width)
        if row_details:
            print_box_line(f"   Info:   {' '.join(row_details)}", width)
        
        short_path = svc['path'].replace(os.path.expanduser("~"), "~")
        print_box_line(f"   Origin: {short_path}", width)
        
        if ports_str:
            print_box_line(f"   Ports:  {ports_str}", width)

        # Child Containers
        if child_items:
            print_box_line("", width) # Spacer
            for c in child_items:
                c_color = Colors.GREEN if c['state'] == "running" else Colors.RED
                c_ports = format_ports(c['ports'])
                p_info = f" (Ports: {c_ports})" if c_ports else ""
                
                print_box_line(f"   ├─ {c_color}{c['name']}{Colors.RESET} [{c['state']}]", width)
                print_box_line(f"   │  Img: {c['image'][:50]}", width)
                if c_ports:
                    print_box_line(f"   │  Net: {c_ports}", width)

        print_box_line("", width) # Spacer
        if i < len(sorted_svcs) - 1:
            print(f"{Colors.CYAN}├{'─' * (width - 2)}┤{Colors.RESET}")
            print_box_line("", width) # Spacer

    # Orphans
    orphans = [c for name, c in containers.items() if name not in processed_containers and not name.startswith("run-")]
    if orphans:
        print(f"{Colors.CYAN}├{'─' * (width - 2)}┤{Colors.RESET}")
        print_box_line("", width) # Spacer
        print_box_line(f"{Colors.YELLOW}⚠️  UNMANAGED CONTAINERS (Orphans){Colors.RESET}", width, bold=True)
        for c in orphans:
            c_ports = format_ports(c['ports'])
            print_box_line(f"   {I_CONT} {c['name']} ({c['state']})", width)
            if c_ports:
                print_box_line(f"      Ports: {c_ports}", width)
        print_box_line("", width) # Spacer

    # Bottom Border
    print(f"{Colors.CYAN}└{'─' * (width - 2)}┘{Colors.RESET}\n")

if __name__ == "__main__":
    main()

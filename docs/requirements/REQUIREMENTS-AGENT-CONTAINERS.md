# REQUIREMENTS: Dockerised Agent Isolation

## Purpose

Define how AMI-AGENTS builds, configures, and runs AI coding agents (Claude, Qwen, Gemini) inside Docker/Podman containers with full filesystem isolation, credential management, bidirectional rsync with change detection, explicit network whitelisting, and persistent workspaces.

## Scope

This is an **AMI-AGENTS-level** feature (not project-specific). It applies to any agent invocation — whether from the CLI (`ami-agent`), from a web chat backend (AMI-TRADING), or from CI pipelines. The container is the universal execution sandbox.

## Actors

- **Host User** — the human operator on the host machine who configures and launches agents
- **Agent User** — non-root user inside the container running the agent CLI subprocess
- **Root (container)** — controls file locks, volume permissions, network rules inside the container
- **Sync Daemon** — watches for file changes and proposes bidirectional rsync events

---

## Reference Architecture

```
HOST MACHINE
├── ~/.claude/          ─── rsync ──→  /home/agent/.claude/     (RO or RW, configurable)
├── ~/.config/qwen/     ─── rsync ──→  /home/agent/.config/qwen/ (RO or RW)
├── /home/ami/AMI-AGENTS/ ── rsync ──→  /workspace/AMI-AGENTS/   (bidirectional, selective)
│
├── agent-volumes/
│   ├── {agent-id}/workspace/  ←── persistent named volume
│   ├── {agent-id}/transcripts/ ←── persistent named volume
│   └── {agent-id}/cache/      ←── persistent named volume
│
└── agent-sync.yaml     ─── config for rsync rules, change detection, auto-sync triggers

CONTAINER (ami-agent:{tag})
├── /home/agent/         ── agent user home (UID matches host)
├── /workspace/          ── rsync'd project files (bidirectional sync)
├── /credentials/        ── rsync'd credentials (read-only by default)
├── /transcripts/        ── persistent volume (agent transcript logs)
├── /cache/              ── persistent volume (.boot-linux, .venv, node_modules)
│
├── Network: explicit whitelist only (iptables DROP default + ACCEPT per IP:port)
├── User: agent (non-root, UID mapped to host via --userns=keep-id)
└── Root: controls file locks, immutable attrs, volume permissions
```

---

## Functional Requirements

### 1. Container Image Build

#### FR-1.1: Base Dockerfile

The AMI-AGENTS repo MUST provide a `Dockerfile.agent` (or `Containerfile.agent`) at the repo root that builds a complete agent execution environment.

Base image: `python:3.11.14-slim-bookworm` (matching existing `pyproject.toml` constraint `==3.11.*`).

The image MUST include:
- Python 3.11 + uv (pinned version)
- Node.js 20.x (for claude, qwen, gemini CLIs)
- git, curl, rsync, inotify-tools (for change detection)
- iptables (for network whitelisting enforcement)
- Non-root `agent` user with configurable UID (default: 1000)

Reference: existing `projects/AMI-TRADING/res/docker/Dockerfile.agent` for pattern.

**Acceptance criteria**: `podman build -f Dockerfile.agent -t ami-agent:latest .` succeeds. The image contains python, node, git, rsync, iptables. The `agent` user exists.

#### FR-1.2: Configurable Tool Installation via CI YAML

The Dockerfile MUST accept a build argument pointing to a YAML file that specifies which tools to install:

```dockerfile
ARG INSTALL_CONFIG=ami/config/install-defaults.yaml
COPY ${INSTALL_CONFIG} /tmp/install-config.yaml
RUN make install-ci INSTALL_DEFAULTS=/tmp/install-config.yaml
```

This reuses the existing `make install-ci` target which reads `install-defaults.yaml`. Users can inject a custom YAML to control which of the ~24 bootstrap tools are installed.

Example custom config:
```yaml
# agent-install-minimal.yaml — lightweight agent image
components:
  - uv
  - python
  - git
  - openssh
```

Example full config:
```yaml
# agent-install-full.yaml — everything
components:
  - uv
  - python
  - git
  - go
  - podman
  - openssh
  - openssl
  - ansible
  - rust
  - playwright
```

**Acceptance criteria**: Building with `--build-arg INSTALL_CONFIG=my-config.yaml` installs only the specified components. The existing `make install-ci` machinery handles the actual installation.

#### FR-1.3: Agent CLI Installation

The image MUST install the AI coding agent CLIs as part of the build:

```dockerfile
RUN npm install @anthropic-ai/claude-code@latest
RUN npm install @anthropic-ai/qwen-code@latest  # or equivalent
RUN npm install -g @google/gemini-cli@0.28.2
RUN make register-extensions
```

The specific CLIs to install MUST be configurable (not all agents needed in every image).

**Acceptance criteria**: `claude --version`, `qwen --version`, `gemini --version` work inside the container (for installed agents).

---

### 2. Credential Management via Rsync

#### FR-2.1: Credential Rsync with Permission Modes

Agent credentials MUST be synced from host to container via rsync (NOT Docker bind mounts — rsync gives fine-grained control over what's copied and when).

Configurable credential sources in `agent-sync.yaml`:

```yaml
credentials:
  - source: ~/.claude/
    dest: /credentials/.claude/
    mode: readonly        # readonly | readwrite | locked
    include:
      - "settings.json"
      - "credentials.json"
      - "*.key"
    exclude:
      - "projects/"       # no project-specific state
      - "memory/"          # no memory leakage between agents

  - source: ~/.config/qwen/
    dest: /credentials/.config/qwen/
    mode: readonly

  - source: ~/.config/gemini/
    dest: /credentials/.config/gemini/
    mode: locked          # immutable — cannot be modified even by root
```

Permission modes:
- **readonly**: rsync'd into container, `chattr +i` set by root (agent user cannot modify)
- **readwrite**: rsync'd bidirectionally (changes inside container can sync back to host)
- **locked**: rsync'd once at container creation, then made immutable AND excluded from future syncs

**Acceptance criteria**: Credentials are available inside the container at the specified paths. `readonly` files cannot be modified by the agent user. `locked` files cannot be modified by anyone including root.

#### FR-2.2: Credential Sync Triggers

Credential sync MUST happen:
1. On container creation (initial rsync)
2. On explicit `ami-agent sync credentials` command
3. NOT automatically during agent execution (prevents credential leakage mid-session)

**Acceptance criteria**: Credentials are NOT live-mounted. Changes to host credentials require explicit sync to propagate.

---

### 3. Bidirectional Workspace Rsync with Change Detection

#### FR-3.1: Workspace Sync Configuration

Project workspaces MUST be synced bidirectionally between host and container via rsync with selective rules:

```yaml
workspaces:
  - name: ami-agents
    source: /home/ami/AMI-AGENTS/
    dest: /workspace/AMI-AGENTS/
    direction: bidirectional    # host-to-container | container-to-host | bidirectional
    auto_sync: on_change        # on_change | manual | on_session_start | on_session_end
    conflict_resolution: ask    # ask | host-wins | container-wins | newest-wins
    exclude:
      - ".git/"
      - "node_modules/"
      - ".venv/"
      - "__pycache__/"
      - "logs/"
      - ".boot-linux/"
    include_override: []        # force-include patterns that would otherwise be excluded
    max_file_size_mb: 50        # skip files larger than this
```

**Acceptance criteria**: Files modified on host appear in container after sync. Files modified in container can be synced back to host. Excluded paths are never synced.

#### FR-3.2: Change Detection via Host-Side inotifywait

A sync daemon MUST run on the **host only**, watching for file changes using `inotifywait` (from `inotify-tools`):

- Watches: CREATE, MODIFY, DELETE, MOVED_TO events on the host workspace
- Also polls the container workspace periodically (configurable, default 10s) via `rsync --dry-run` to detect container-side changes
- Debounce: 2 seconds (configurable) — coalesces rapid changes into one sync event
- Filters: respects the exclude/include rules from workspace config

When changes are detected:
1. Generate a diff summary (files added, modified, deleted — with sizes)
2. Propose the sync to the user (or auto-sync if `auto_sync: on_change`)
3. On approval, run rsync with `--dry-run` first, then actual sync
4. Log the sync event to the agent transcript

The daemon runs as a host process (NOT inside the container) managed by systemd user unit or as a background thread in `ami-agent`.

**Acceptance criteria**: Modifying a file on the host triggers a sync proposal within 5 seconds. Container-side changes are detected within the poll interval. Auto-sync mode skips the approval step.

#### FR-3.3: Conflict Resolution

When the same file is modified on both host and container between syncs:

- **ask** (default): show both versions with diff, let user choose
- **host-wins**: host version always overwrites container
- **container-wins**: container version always overwrites host
- **newest-wins**: most recent mtime wins

**Acceptance criteria**: Conflicting edits do not silently overwrite. The configured resolution strategy is applied.

#### FR-3.4: Selective Sync

The user MUST be able to sync individual files or directories, not just entire workspaces:

```bash
ami-agent sync workspace ami-agents --path src/core/pipeline.py    # single file
ami-agent sync workspace ami-agents --path src/delivery/            # directory
ami-agent sync workspace ami-agents --direction host-to-container   # override direction
ami-agent sync workspace ami-agents --dry-run                       # preview only
```

**Acceptance criteria**: Partial sync works. `--dry-run` shows what would change without modifying anything.

---

### 4. User Model and File Locks

#### FR-4.1: Non-Root Agent User

The container MUST run the agent as a non-root user `agent` with UID matching the host user (default: 1000, configurable).

```dockerfile
ARG AGENT_UID=1000
ARG AGENT_GID=1000
RUN groupadd -g ${AGENT_GID} agent && useradd -u ${AGENT_UID} -g agent -m agent
USER agent
```

When using Podman rootless: `--userns=keep-id` maps the host UID directly into the container, avoiding subordinate UID permission issues with bind mounts.

**Acceptance criteria**: `whoami` inside the container returns `agent`. Files created by the agent are owned by the host user's UID on bind-mounted volumes.

#### FR-4.2: Root-Controlled File Locks

Root inside the container MUST be able to set immutable attributes on files that the agent user cannot modify:

```bash
# Set by entrypoint script running as root before dropping to agent user
chattr +i /credentials/.claude/credentials.json
chattr +i /workspace/AMI-AGENTS/ami/config/automation.yaml
```

A lock manifest MUST be configurable:

```yaml
file_locks:
  - path: /credentials/              # entire directory tree
    recursive: true
  - path: /workspace/AMI-AGENTS/ami/config/
    recursive: true
  - path: /workspace/AMI-AGENTS/.env
```

The entrypoint script MUST:
1. Run as root
2. Apply file locks from manifest
3. Drop to agent user via `exec su - agent`

**Acceptance criteria**: The agent user cannot modify locked files (`Operation not permitted`). Root can unlock files for maintenance.

#### FR-4.3: Persistent Volumes

Each agent instance MUST have persistent named volumes that survive container restarts:

```yaml
volumes:
  - name: {agent-id}-workspace
    mount: /workspace/
    driver: local
  - name: {agent-id}-transcripts
    mount: /transcripts/
    driver: local
  - name: {agent-id}-cache
    mount: /cache/
    driver: local
    description: ".boot-linux, .venv, node_modules — expensive to rebuild"
```

Volumes MUST be named with the agent ID prefix for easy identification and cleanup.

**Acceptance criteria**: Stopping and restarting a container preserves workspace files, transcripts, and cached dependencies. `podman volume ls` shows named volumes with agent ID prefix.

---

### 5. Network Isolation

#### FR-5.1: Default-Deny Network Policy

Containers MUST start with a default-deny egress policy. All outbound traffic is blocked unless explicitly whitelisted.

Implementation: the entrypoint script (running as root) applies iptables rules before dropping to agent user:

```bash
# Default deny all outbound
iptables -P OUTPUT DROP
iptables -A OUTPUT -o lo -j ACCEPT          # allow loopback
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT  # allow responses

# Apply whitelist from config
while IFS=: read -r ip port proto; do
    iptables -A OUTPUT -p "${proto:-tcp}" -d "$ip" --dport "$port" -j ACCEPT
done < /etc/ami-agent/network-whitelist.conf
```

Requires `--cap-add=NET_ADMIN` on container launch (dropped after iptables setup, before agent user).

**Acceptance criteria**: The agent cannot reach any IP:port not in the whitelist. `curl google.com` fails. `curl api.anthropic.com:443` succeeds (if whitelisted).

#### FR-5.2: Configurable Network Whitelist

The whitelist MUST be defined in the agent config:

```yaml
network:
  policy: whitelist              # whitelist | allow-all | deny-all
  dns:
    - 1.1.1.1                   # Cloudflare DNS
    - 8.8.8.8                   # Google DNS
  whitelist:
    # AI provider APIs
    - host: api.anthropic.com
      port: 443
      protocol: tcp
      description: Claude API
    - host: generativelanguage.googleapis.com
      port: 443
      protocol: tcp
      description: Gemini API

    # Package registries
    - host: registry.npmjs.org
      port: 443
      description: npm packages
    - host: pypi.org
      port: 443
      description: Python packages
    - host: files.pythonhosted.org
      port: 443
      description: Python package downloads

    # Git hosting
    - host: github.com
      port: 443
      description: GitHub
    - host: github.com
      port: 22
      protocol: tcp
      description: GitHub SSH

    # Local services (AMI-TRADING infra)
    - host: 127.0.0.1
      port: 5433
      description: TimescaleDB
    - host: 127.0.0.1
      port: 9000
      description: MinIO
```

Hostnames MUST be resolved via a local DNS proxy (e.g. dnsmasq) running inside the container that ONLY resolves whitelisted hostnames. This blocks DNS-based data exfiltration — the agent cannot resolve arbitrary domains.

**Acceptance criteria**: Only traffic to whitelisted IP:port combinations is allowed. The whitelist is readable and auditable.

#### FR-5.3: Network Policy Modes

Three modes for different use cases:
- **whitelist** (default): only explicitly allowed destinations
- **allow-all**: no restrictions (for trusted development)
- **deny-all**: complete network isolation (for offline analysis)

**Acceptance criteria**: Each mode is selectable via config. `deny-all` blocks everything including DNS.

#### FR-5.4: Dynamic Network Access Requests

Agents MUST be able to request access to new network destinations via a tool call during execution. The flow:

1. Agent emits a network access request (e.g., via a shell command or tool call): `ami-agent-request-network --host example.com --port 443 --reason "Need to fetch API docs"`
2. The request is forwarded to the host-side sync daemon / management CLI
3. The human operator sees the request with the agent's stated reason
4. On approval: the iptables rule is added dynamically inside the running container (via `podman exec`)
5. On denial: the agent is informed the request was rejected
6. All requests (approved and denied) are logged to the sync journal

The request tool MUST be available as an OBSERVE-tier command (no side effects until approved).

**Acceptance criteria**: An agent can request network access to a new destination. The request requires human approval. Approved rules take effect without container restart.

#### FR-5.5: Inter-Agent Networking

Agent containers MUST be configurable for inter-agent communication:

- **Default**: fully isolated (no shared network)
- **Opt-in**: specific agents can join a shared Podman network (`ami-agent-mesh`) via config

```yaml
network:
  policy: whitelist
  agent_mesh: true              # join shared agent network
  agent_mesh_name: ami-agents   # Podman network name
```

Agents on the mesh can reach each other by container name (Podman DNS). Agents NOT on the mesh cannot reach any other agent.

**Acceptance criteria**: Two agents with `agent_mesh: true` can reach each other. An agent with `agent_mesh: false` cannot reach any other agent container.

#### FR-5.6: Rsync Partial Transfer and Resume

Interrupted rsync operations MUST resume where they left off using `rsync --partial --partial-dir=.rsync-partial`:

- Partially transferred files are stored in `.rsync-partial/` inside the destination
- On resume, rsync picks up from the partial file instead of re-transferring
- The `.rsync-partial/` directory is cleaned up after successful completion
- Container stop MUST NOT corrupt partially-synced files (the partial dir isolates them)

**Acceptance criteria**: Interrupting a large sync and re-running completes without re-transferring already-synced data. No inconsistent files in the workspace.

---

### 5b. Multi-Host Deployment

#### FR-5.7: Remote Agents via Rsync over SSH

Agent workspaces MUST be syncable to/from remote hosts via rsync over SSH:

```yaml
workspaces:
  - name: ami-agents
    source: /home/ami/AMI-AGENTS/
    dest: ssh://remote-host:/workspace/AMI-AGENTS/
    direction: bidirectional
    ssh_key: ~/.ssh/id_ed25519
    ssh_port: 22
```

The same sync daemon, change detection, and conflict resolution logic applies — the only difference is the rsync transport (SSH instead of local).

**Acceptance criteria**: `ami-agent sync my-remote-agent` syncs workspace to a remote host via SSH. Change detection works across hosts (via periodic `rsync --dry-run` over SSH).

---

### 6. Agent Provisioning

#### FR-6.1: Agent Creation Script

A single command MUST create a fully configured agent container:

```bash
ami-agent create \
  --name my-research-agent \
  --provider claude \
  --model claude-sonnet-4-5 \
  --config agents/research-profile.yaml \
  --network-policy whitelist \
  --workspace /home/ami/AMI-AGENTS
```

This MUST:
1. Build the image if not cached (or pull from registry)
2. Create named volumes
3. Initial rsync of workspace and credentials
4. Apply file locks
5. Apply network whitelist
6. Start the container
7. Register the agent in a local manifest (`~/.ami/agents.yaml`)

**Acceptance criteria**: A single command produces a running, fully configured agent container. The agent is listed in `ami-agent list`.

#### FR-6.2: Agent Lifecycle Commands

```bash
ami-agent list                    # list all agents with status
ami-agent start {name}            # start a stopped agent
ami-agent stop {name}             # stop a running agent (graceful)
ami-agent restart {name}          # stop + start
ami-agent destroy {name}          # remove container + volumes (with confirmation)
ami-agent shell {name}            # exec into container as agent user
ami-agent root-shell {name}       # exec into container as root (for lock management)
ami-agent logs {name}             # tail container logs
ami-agent sync {name}             # trigger workspace sync
ami-agent status {name}           # detailed status (uptime, resource usage, sync state)
```

**Acceptance criteria**: All lifecycle commands work. `destroy` requires confirmation and removes all persistent state.

#### FR-6.3: Ansible Template for Fleet Provisioning

An Ansible playbook MUST be provided for creating multiple agents at once:

```yaml
# agents/fleet.yml
agents:
  - name: claude-research
    provider: claude
    model: claude-sonnet-4-5
    config: agents/readonly-profile.yaml
    network: agents/research-network.yaml
    workspace: /home/ami/AMI-AGENTS

  - name: qwen-codegen
    provider: qwen
    model: qwen-coder
    config: agents/codegen-profile.yaml
    network: agents/codegen-network.yaml
    workspace: /home/ami/AMI-AGENTS
```

```bash
ami ansible agents/fleet.yml
```

**Acceptance criteria**: Running the playbook creates all specified agents. Idempotent — running again updates config without recreating.

#### FR-6.4: ACP (Agent Communication Protocol) Adoption

Agent management MUST adopt the ACP/A2A protocol patterns for inter-agent communication and external agent discovery:

- Each agent container MUST publish an **Agent Card** (JSON descriptor) at a well-known path inside the container and on the host manifest:

```json
{
  "name": "claude-research",
  "provider": "claude",
  "model": "claude-sonnet-4-5",
  "capabilities": ["code_read", "web_search", "web_fetch"],
  "network_policy": "whitelist",
  "status": "running",
  "endpoint": "unix:///run/ami-agents/claude-research.sock",
  "created": "2026-03-26T12:00:00Z"
}
```

- Agent-to-agent communication (when on shared mesh) MUST use JSON-RPC 2.0 over Unix domain sockets or HTTP
- The CLI (`ami-agent`) MUST be the primary management interface, with ACP-compatible agent discovery built in:

```bash
ami-agent discover                    # list all agent cards (local + mesh)
ami-agent send {name} "instruction"   # send a task to a running agent
ami-agent ask {name} "question"       # query an agent and get response
```

This enables future integration with external A2A-compatible agent platforms.

**Acceptance criteria**: Each running agent has a discoverable Agent Card. `ami-agent discover` lists all agents with their capabilities and status.

---

### 7. Security Model

#### FR-7.1: Container Security Flags

All agent containers MUST run with:

```bash
podman run \
  --userns=keep-id \
  --cap-drop=ALL \
  --cap-add=NET_ADMIN \           # for iptables setup only (dropped after)
  --security-opt=no-new-privileges \
  --security-opt=seccomp=default \
  --read-only \                    # root filesystem read-only
  --tmpfs /tmp:rw,noexec,nosuid \  # writable /tmp without exec
  --tmpfs /run:rw,noexec,nosuid \
  ...
```

After iptables setup, `NET_ADMIN` MUST be dropped by the entrypoint (cannot be done via Podman flags — done via `capsh --drop=cap_net_admin` in entrypoint).

**Acceptance criteria**: The container runs with minimal capabilities. The agent user cannot escalate privileges.

#### FR-7.2: Read-Only Root Filesystem

The container root filesystem MUST be mounted read-only (`--read-only`). Writable areas are limited to:
- `/workspace/` — project files (persistent volume)
- `/transcripts/` — agent logs (persistent volume)
- `/cache/` — dependency caches (persistent volume)
- `/tmp/` — tmpfs, ephemeral
- `/home/agent/` — user home (persistent volume or tmpfs)

**Acceptance criteria**: The agent cannot modify system files. `touch /usr/bin/evil` fails.

#### FR-7.3: Resource Limits

Each agent container MUST have configurable resource limits:

```yaml
resources:
  memory: 4G          # hard limit
  memory_swap: 4G     # no swap (memory == memory_swap)
  cpus: 2.0           # CPU quota
  pids_limit: 256     # max processes
  ulimits:
    nofile: 4096      # max open files
```

**Acceptance criteria**: An agent that exceeds memory limit is OOM-killed. CPU-bound agents don't starve the host.

---

### 8. Monitoring and Observability

#### FR-8.1: Agent Status Dashboard

`ami-agent status` MUST show:
- Container state (running/stopped/crashed)
- Uptime
- CPU/memory usage (from `podman stats`)
- Network traffic summary (bytes in/out, blocked connection attempts)
- Last sync timestamp and status
- Active transcript session
- Disk usage per volume

**Acceptance criteria**: `ami-agent status my-agent` displays all metrics in a readable format.

#### FR-8.2: Sync Event Log

All rsync operations MUST be logged to a sync journal:

```
~/.ami/sync-log/{agent-id}.jsonl
```

Each entry:
```json
{
  "timestamp": "2026-03-26T12:00:00Z",
  "direction": "host-to-container",
  "workspace": "ami-agents",
  "files_added": 3,
  "files_modified": 1,
  "files_deleted": 0,
  "bytes_transferred": 45230,
  "duration_ms": 340,
  "triggered_by": "auto_change_detection"
}
```

**Acceptance criteria**: Every sync operation is logged. `ami-agent sync-log my-agent` shows recent syncs.

---

## Non-Functional Requirements

### NFR-1: Build Time
A minimal agent image (python + node + git + one agent CLI) MUST build in under 5 minutes on a warm Docker cache.

### NFR-2: Startup Time
Container startup (from `podman run` to agent ready) MUST complete in under 10 seconds, excluding initial workspace rsync.

### NFR-3: Sync Latency
Change detection to sync proposal MUST happen within 5 seconds of file modification. Actual rsync MUST complete within 30 seconds for typical workspace sizes (<1GB).

### NFR-4: Podman Compatibility
All container operations MUST work with Podman rootless. Docker compatibility is a secondary goal.

### NFR-5: Idempotency
All provisioning operations (`create`, `sync`, `apply-locks`) MUST be idempotent. Running them twice produces the same result.

---

## Constraints

- MUST use Podman as primary container engine (already bootstrapped in AMI-AGENTS)
- MUST NOT require Docker Desktop or Docker daemon
- MUST NOT require root on the host (Podman rootless)
- MUST reuse existing `make install-ci` and bootstrap infrastructure inside the container
- MUST NOT store credentials in Docker images (only rsync'd at runtime)
- Network whitelist MUST be enforceable — the agent user cannot modify iptables rules

## Dependencies

- Podman (already bootstrapped: `ami/scripts/bootstrap/bootstrap_podman.sh`)
- rsync (system package, installed in Dockerfile)
- inotify-tools (for change detection, installed in Dockerfile)
- iptables (for network whitelisting, installed in Dockerfile)
- Ansible (for fleet provisioning, already bootstrapped)

## Resolved Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Sync daemon location | **Host only** — inotifywait on host, periodic rsync --dry-run poll for container changes |
| 2 | DNS resolution for whitelists | **Local DNS proxy** (dnsmasq) inside container, only resolves whitelisted hostnames |
| 3 | Inter-agent networking | **Configurable per agent** — default isolated, opt-in to shared `ami-agent-mesh` network |
| 4 | Dynamic network access | **Yes, with human approval** — agent requests via tool call, operator approves, iptables rule added dynamically |
| 5 | Large binary files in rsync | **Always sync everything** — rsync handles efficiently with checksums, no size filtering |
| 6 | In-flight rsync on container stop | **rsync --partial + resume** — partial files in `.rsync-partial/` dir, resume on next sync |
| 7 | Management interface | **CLI + ACP protocol** — `ami-agent` CLI with ACP/A2A agent discovery and communication |
| 8 | Multi-host deployment | **rsync over SSH** — same model as local, SSH transport for remote workspaces |

## Remaining Open Questions

1. How should the entrypoint drop `NET_ADMIN` capability after iptables setup? `capsh --drop` only works for the current process tree — need to verify it propagates to agent subprocess.
2. Should the dnsmasq proxy inside the container be configurable (custom upstream DNS), or hardcoded to the whitelisted resolvers?
3. What's the ACP/A2A version target? The protocol is evolving — should we pin to a specific spec version or track latest?
4. How should agent-to-agent task delegation work? Direct JSON-RPC, or via the host CLI as intermediary?
5. Should there be a web UI for agent fleet management in a future version?

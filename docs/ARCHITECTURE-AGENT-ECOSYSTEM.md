# AMI Agent Ecosystem — Cross-Repo Architecture

> How containerised AI agents, the gateway, chat UI, task engine, and A2A protocol connect across AMI-AGENTS, AMI-TRADING, and AMI-SRP.

---

## System Overview

```mermaid
graph TD
    subgraph BROWSER["Browser Clients"]
        TRADING_UI["AMI-TRADING<br/><i>Chat Sidebar (SSE)</i>"]
        SRP_UI["AMI-SRP<br/><i>Ops Center + Agent Chat</i>"]
        PORTAL_UI["AMI-PORTAL<br/><i>Workspace</i>"]
    end

    subgraph HOST["Agent Host"]
        GW["ami-agentd serve<br/><i>Rust/Axum :8900</i><br/><i>OIDC, A2A proxy, interaction logs</i>"]
        CLI["ami-agentd CLI<br/><i>create/start/stop/sync</i>"]
        DB[("SQLite / PostgreSQL<br/><i>interaction logs</i>")]

        subgraph CONTAINERS["Podman Containers"]
            C1["claude-research<br/><i>A2A Starlette + BootloaderAgent</i><br/><i>UDS: a2a.sock</i>"]
            C2["qwen-codegen<br/><i>A2A Starlette + BootloaderAgent</i><br/><i>UDS: a2a.sock</i>"]
            MESH[".mesh/<br/><i>shared UDS dir</i>"]
        end
    end

    subgraph EXTERNAL["External APIs"]
        CLAUDE_API["api.anthropic.com"]
        GEMINI_API["googleapis.com"]
    end

    TRADING_UI -- "POST + SSE<br/>A2A v0.3" --> GW
    SRP_UI -- "POST + SSE" --> GW
    PORTAL_UI -- "POST + SSE" --> GW
    GW -- "UDS" --> C1 & C2
    GW --> DB
    CLI -- "UDS (local)" --> C1 & C2
    CLI -- "podman CLI" --> CONTAINERS
    CLI -- "rsync (on demand)" --> C1 & C2
    C1 -. "UDS via .mesh/" .-> C2
    C1 -- "HTTPS (whitelisted)" --> CLAUDE_API
    C2 -- "HTTPS (whitelisted)" --> GEMINI_API
```

---

## Component Responsibilities

| Component | Repo | Language | Responsibility |
|-----------|------|----------|----------------|
| **ami-agent** | AMI-AGENTS | Python | The agent itself (BootloaderAgent, ReAct loop). Runs on host AND inside containers. |
| **ami-agentd** | AMI-AGENTS | Rust (Axum) | Single binary: CLI (`create/start/stop/sync`) + gateway server (`serve`). Manages containers via podman, proxies A2A to agent UDS, OIDC auth, TLS, interaction logs (SQLite/PG). **Host only** — disabled inside containers (`AMI_CONTAINER=1`). |
| **Agent Container** | AMI-AGENTS | Python (Starlette + BootloaderAgent) | Runs A2A server on UDS. Executes claude/qwen CLI subprocesses. Isolated filesystem, network whitelist. |
| **Chat Sidebar** | AMI-TRADING | React/TypeScript | Browser UI. Sends POST, receives SSE. Talks to gateway, not agents directly. |
| **srp-tasks** | AMI-SRP | Rust | TODO/planning task engine. Operational task tracking, NOT execution. State machine + PostgreSQL + NATS. |
| **SRP Ops Center** | AMI-SRP | Rust + React | Future: ontology-grounded agent chat, agent monitoring panel. |

---

## Communication Paths

```mermaid
graph LR
    subgraph LOCAL["Same Host"]
        CLI_L["ami-agentd CLI"] -- "UDS" --> AGENT_L["Agent Container"]
        GW_L["Gateway"] -- "UDS" --> AGENT_L
        AGENT_L -- "UDS (.mesh/)" --> AGENT_L2["Other Agent"]
    end

    subgraph REMOTE["Cross-Host"]
        BROWSER_R["Browser"] -- "HTTPS POST + SSE :8900" --> GW_R["Gateway"]
        SERVICE_R["AMI-SRP Backend"] -- "HTTPS :8900" --> GW_R
    end

    subgraph OUTBOUND["Agent → Internet"]
        AGENT_O["Agent"] -- "HTTPS (iptables whitelist)" --> API["LLM API / Package Registry"]
    end
```

| Path | Transport | Auth | Notes |
|------|-----------|------|-------|
| Browser → Agent | HTTPS POST+SSE → Gateway → UDS | OIDC JWT | Gateway handles TLS + auth |
| CLI → Agent | UDS direct | Filesystem perms | No network, no auth needed |
| Agent ↔ Agent | UDS via `.mesh/` | Mount = access | Only mesh members |
| Agent → LLM API | HTTPS outbound | API key (rsync'd credential) | iptables whitelist enforced |
| Agent → Package Registry | HTTPS outbound | None | DNS whitelist (dnsmasq) |

---

## Data Flow: Chat Message

```mermaid
sequenceDiagram
    participant B as Browser (Chat Sidebar)
    participant G as Gateway (:8900)
    participant A as Agent Container (UDS)
    participant LLM as Claude/Qwen CLI

    B->>G: POST /agents/claude-research/messages:stream<br/>Authorization: Bearer {jwt}
    G->>G: Validate JWT (OIDC)
    G->>G: Validate A2A message schema
    G->>G: Create interaction log in PostgreSQL
    G->>A: Forward A2A SendStreamingMessage (UDS)
    A->>A: asyncio.to_thread(BootloaderAgent.run)
    A->>LLM: subprocess: claude --print <instruction>
    loop Streaming chunks
        LLM-->>A: StreamEvent (stdout line)
        A-->>G: SSE: TaskArtifactUpdateEvent (UDS)
        G-->>B: SSE: TaskArtifactUpdateEvent (HTTPS)
    end
    A->>A: Shell block? → validate hooks → execute
    A-->>G: SSE: TaskStatusUpdateEvent (completed)
    G->>G: Update interaction log
    G-->>B: SSE: Task (final)
```

---

## Security Layers

```mermaid
graph TD
    subgraph LAYER1["Layer 1: Network"]
        FW["iptables default-deny<br/>+ explicit whitelist"]
        DNS["dnsmasq: only whitelisted hostnames resolve"]
        UDS["No TCP ports exposed<br/>UDS only"]
    end

    subgraph LAYER2["Layer 2: Container"]
        CAPS["cap-drop=ALL<br/>no-new-privileges"]
        RO["Read-only root filesystem"]
        USER["Non-root agent user (gosu)"]
        LOCKS["chattr +i on credentials"]
        RESOURCE["Memory/CPU/PID limits"]
    end

    subgraph LAYER3["Layer 3: Agent"]
        SCOPE["ScopeOverride<br/>observe=allow, rest=deny"]
        HOOKS["Hook validators<br/>PRE_BASH, PRE_EDIT, POST_OUTPUT"]
        TOOLS["allowed_tools<br/>Read, WebSearch, WebFetch only"]
        ALLOW["execute_allow<br/>ami-browser only"]
    end

    subgraph LAYER4["Layer 4: Gateway"]
        OIDC["Multi-issuer OIDC JWT validation"]
        A2A_VAL["A2A message schema validation"]
        LOG["Structured audit logging"]
    end

    LAYER1 --> LAYER2 --> LAYER3
    LAYER4 --> LAYER1
```

---

## Repo-Level Requirements Index

| Requirement Document | Repo | Path |
|---------------------|------|------|
| Agent Container Isolation | AMI-AGENTS | `docs/requirements/REQUIREMENTS-AGENT-CONTAINERS.md` |
| Chat Agent Security Profile | AMI-TRADING | `docs/requirements/REQUIREMENTS-CHAT-AGENT-PROFILE.md` |
| Chat Backend (Gateway + A2A) | AMI-TRADING | `docs/requirements/REQUIREMENTS-CHAT-BACKEND.md` |
| Chat UI (Sidebar) | AMI-TRADING | `docs/requirements/REQUIREMENTS-CHAT-UI.md` |
| Task Engine (TODO/Planning) | AMI-SRP | `docs/requirements/REQUIREMENTS-TASK-ENGINE.md` |
| This document | AMI-AGENTS | `docs/ARCHITECTURE-AGENT-ECOSYSTEM.md` |

---

## Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent execution | Containerised always (Podman) | Isolation, reproducibility, network control |
| Agent communication | A2A v0.3 over UDS | Standard protocol, no TCP exposure |
| Streaming | SSE (not WebSocket) | A2A-native, supports auth headers, HTTP/3 efficient |
| ami-agentd | Single Rust binary: CLI + gateway | Container mgmt + A2A proxy in one binary, like `podman` CLI + `podman system service` |
| Interaction logs | Gateway owns, SRP PostgreSQL | Audit/observability records (NOT srp-tasks which is TODO/planning) |
| Agent provisioning | `ami-agentd` CLI wrapping `podman` + Podman labels for metadata | No custom registry, no manifest files — `podman ps` IS the registry |
| Container→host sync | `ami-agentd sync` (rsync on demand) | No daemon, no inotifywait, user syncs when needed |
| Credentials | Bind mount `:ro` | Not rsync — host changes visible immediately, agent can't modify |
| Agent upgrades | In-place npm update | Fast iteration, no image rebuild |
| Monitoring | systemd journal + CLI | Simple, local-only, no external stack |
| ami-browser access | `execute_allow` in ScopeOverride | Per-command allowlist, minimal tier system change |
| srp-tasks | TODO/planning system, not job queue | Humans manage tasks, Prefect handles execution |

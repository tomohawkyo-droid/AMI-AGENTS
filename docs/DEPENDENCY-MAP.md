# AMI Dependency Map

**Date:** 2026-04-14
**Type:** Architecture Reference

---

## 1. Overview — Category Relationships

High-level view: how the major groups depend on each other.

```mermaid
graph LR
    classDef grp fill:#e8e8e8,stroke:#666,stroke-width:2px,color:#333

    SYS["System Prerequisites\ngit, curl, openssh, openssl\nrsync, openvpn"]:::grp
    BOOT["Bootstrap Components\nuv, python, gcc, rust, go\npandoc, podman, k8s, ..."]:::grp
    EXT["Extensions\n22 CLI commands\n6 categories"]:::grp
    CONTAINERS["Containers\nKeycloak, OpenBao, PostgreSQL\nRedis, Vaultwarden, Prometheus"]:::grp
    PROJECTS["Projects\nAMI-STREAMS, AMI-DATAOPS\nAMI-PORTAL, AMI-TRADING, ..."]:::grp
    CI["AMI-CI\nHooks, checks, linting"]:::grp

    BOOT --> SYS
    EXT --> BOOT
    EXT ==> CONTAINERS
    PROJECTS --> BOOT
    PROJECTS ==> CONTAINERS
    PROJECTS -.-> CI
    CONTAINERS --> BOOT
```

---

## 2. Bootstrap Install Chain

What installs what, in order. Arrows mean "depends on".

```mermaid
graph TB
    classDef phase fill:#2d5a87,stroke:#1a3a5c,color:#fff
    classDef tool fill:#4a7ab5,stroke:#2d5a87,color:#fff

    subgraph P0 ["Phase 0: System (sudo make pre-req)"]
        direction LR
        git[git]:::phase
        curl[curl]:::phase
        openssh[openssh]:::phase
        openssl[openssl]:::phase
        openvpn[openvpn]:::phase
        rsync[rsync]:::phase
    end

    subgraph P1 ["Phase 1: Core Bootstrap"]
        direction LR
        uv[uv]:::tool
        python[Python 3.11]:::tool
        gcc_musl[GCC/musl]:::tool
        gcc_glibc[GCC/glibc]:::tool
        git_xet[Git Xet/LFS]:::tool
    end

    subgraph P2 ["Phase 2: Language Runtimes"]
        direction LR
        rust[Rust 1.93]:::tool
        go_lang[Go]:::tool
        node[Node.js via uv]:::tool
    end

    subgraph P3 ["Phase 3: Tools & Services"]
        direction LR
        pandoc[Pandoc]:::tool
        texlive[TeX Live]:::tool
        wkhtmltopdf[wkhtmltopdf]:::tool
        pdfjam[PDFjam]:::tool
        podman[Podman]:::tool
        k8s[kubectl + helm]:::tool
        gcloud[gcloud SDK]:::tool
        gh[GitHub CLI]:::tool
        hf[HuggingFace CLI]:::tool
        cloudflared[Cloudflared]:::tool
        sd[sd]:::tool
    end

    subgraph P4 ["Phase 4: Agents & Communication"]
        direction LR
        claude[Claude Code]:::tool
        gemini[Gemini CLI]:::tool
        qwen[Qwen Code]:::tool
        matrix_cmdr[Matrix Cmdr]:::tool
        synadm[Synadm]:::tool
        ansible[Ansible]:::tool
        adb[ADB]:::tool
    end

    subgraph P5 ["Phase 5: Project Builds"]
        direction LR
        himalaya[himalaya fork]:::tool
    end

    %% Phase 1 internal
    python --> uv
    gcc_glibc -.-> gcc_musl

    %% Phase 2 deps on Phase 1
    rust --> gcc_glibc
    rust --> uv
    node --> uv

    %% Phase 3 deps
    pdfjam --> texlive
    hf --> python

    %% Phase 4 deps
    claude --> node
    gemini --> node
    qwen --> node
    matrix_cmdr --> python
    synadm --> python
    ansible --> python

    %% Phase 5 deps
    himalaya --> rust
    himalaya --> gcc_glibc
```

---

## 3. Extensions → Bootstrap Dependencies

Each extension (left) and what bootstrap component it needs (right).

### Core & Enterprise Extensions

```mermaid
graph LR
    classDef ext fill:#5a8c5a,stroke:#3a6c3a,color:#fff
    classDef boot fill:#2d5a87,stroke:#1a3a5c,color:#fff
    classDef ctr fill:#8c5a2d,stroke:#6c3a1a,color:#fff,stroke-dasharray:5 5
    classDef sys fill:#666,stroke:#444,color:#fff

    %% Core extensions
    e_agent(ami-agent):::ext --> python[Python]:::boot
    e_ami(ami / ami-run):::ext --> python
    e_repo(ami-repo):::ext --> python
    e_repo --> git[git]:::sys
    e_transcripts(ami-transcripts):::ext --> python

    %% Enterprise extensions
    e_mail(ami-mail):::ext --> rust[Rust]:::boot
    e_mail -. "submodule" .-> himalaya[(himalaya fork)]
    e_chat(ami-chat):::ext --> matrix_cmdr[Matrix Cmdr]:::boot
    e_synadm(ami-synadm):::ext --> synadm_b[Synadm]:::boot
    e_kcadm(ami-kcadm):::ext ==> keycloak{{Keycloak}}:::ctr
    e_browser(ami-browser):::ext --> python
```

### Dev, Docs & Agent Extensions

```mermaid
graph LR
    classDef ext fill:#5a8c5a,stroke:#3a6c3a,color:#fff
    classDef boot fill:#2d5a87,stroke:#1a3a5c,color:#fff
    classDef sys fill:#666,stroke:#444,color:#fff
    classDef hidden fill:#5a8c5a,stroke:#3a6c3a,color:#aaa,stroke-dasharray:3 3

    %% Dev extensions
    e_backup(ami-backup):::ext --> python[Python]:::boot
    e_backup -. "optional" .-> gcloud[gcloud]:::boot
    e_restore(ami-restore):::ext --> python
    e_gcloud(ami-gcloud):::hidden --> gcloud
    e_cron(ami-cron):::ext --> python
    e_ami(ami):::ext --> k8s[kubectl + helm]:::boot

    %% Infra (hidden)
    e_ssh(ami-ssh):::hidden --> openssh[openssh]:::sys
    e_vpn(ami-vpn):::hidden --> openvpn[openvpn]:::sys
    e_tunnel(ami-tunnel):::hidden --> cloudflared[Cloudflared]:::boot
    e_ssl(ami-ssl):::hidden --> openssl[openssl]:::sys

    %% Docs
    e_docs(ami-docs):::ext --> pandoc[Pandoc]:::boot
    e_docs --> wkhtmltopdf[wkhtmltopdf]:::boot
    e_docs --> texlive[TeX Live]:::boot

    %% Agents
    e_claude(ami-claude):::ext --> b_claude[Claude Code]:::boot
    e_gemini(ami-gemini):::ext --> b_gemini[Gemini CLI]:::boot
    e_qwen(ami-qwen):::ext --> b_qwen[Qwen Code]:::boot
```

---

## 4. Project Topology

How AMI projects depend on each other.

```mermaid
graph TB
    classDef root fill:#2d5a87,stroke:#1a3a5c,color:#fff,stroke-width:3px
    classDef proj fill:#e8e8e8,stroke:#666,stroke-width:2px,color:#333
    classDef infra fill:#8c5a2d,stroke:#6c3a1a,color:#fff

    AGENTS[AMI-AGENTS\nWorkspace Root]:::root

    CI[AMI-CI\nHooks & Checks]:::proj
    DATAOPS[AMI-DATAOPS\nData & Infra Services]:::infra
    STREAMS[AMI-STREAMS\nMail, Matrix, Comms]:::proj
    PORTAL[AMI-PORTAL\nUI & Account Mgmt]:::proj
    TRADING[AMI-TRADING\nTrading Platform]:::proj
    BROWSER[AMI-BROWSER\nBrowser Automation]:::proj
    ZK[ZK-PORTAL\nBlockchain Portal]:::proj
    RUST[RUST-TRADING\nRust ZK Workspace]:::proj

    %% All projects depend on workspace root
    CI --> AGENTS
    DATAOPS --> AGENTS
    STREAMS --> AGENTS
    PORTAL --> AGENTS
    TRADING --> AGENTS
    BROWSER --> AGENTS
    ZK --> AGENTS
    RUST --> AGENTS

    %% CI provides hooks to everyone
    DATAOPS -. "hooks" .-> CI
    STREAMS -. "hooks" .-> CI
    PORTAL -. "hooks" .-> CI
    TRADING -. "hooks" .-> CI

    %% DATAOPS provides infrastructure
    PORTAL -- "Keycloak\nOpenBao" --> DATAOPS
    TRADING -- "Keycloak" --> DATAOPS
    STREAMS -. "compose\nservices" .-> DATAOPS
```

---

## 5. Container Service Map

Services deployed via AMI-DATAOPS compose stack.

```mermaid
graph TB
    classDef svc fill:#8c5a2d,stroke:#6c3a1a,color:#fff
    classDef db fill:#2d5a87,stroke:#1a3a5c,color:#fff
    classDef app fill:#5a8c5a,stroke:#3a6c3a,color:#fff

    subgraph compose ["AMI-DATAOPS Compose Stack"]
        direction TB

        subgraph secrets ["Secrets Profile"]
            KC[Keycloak 26.2\n:8082]:::svc
            BAO[OpenBao 2.4.4\n:8200]:::svc
            VW[Vaultwarden 1.35\n:8083]:::svc
        end

        subgraph data ["Data Profile"]
            PG[(PostgreSQL 16\n:5432)]:::db
            REDIS[(Redis 8.6\n:6379)]:::db
            DGRAPH[(Dgraph)]:::db
            MONGO[(MongoDB 8.2\n:27017)]:::db
            PROM[Prometheus\n:9090]:::svc
        end

        subgraph dev ["Dev Profile"]
            SEARX[SearXNG]:::svc
        end
    end

    %% Internal deps
    KC --> PG

    %% Consumer apps
    PORTAL(AMI-PORTAL\n:3000):::app -- "OIDC" --> KC
    TRADING(AMI-TRADING\n:8080):::app -- "OIDC" --> KC
    PORTAL -. "secrets" .-> BAO
```

---

## Summary Table

| Extension | Category | Bootstrap Deps | Dep Type | Project |
|-----------|----------|---------------|----------|---------|
| ami-agent | core | python | binary | AGENTS |
| ami / ami-run | core | python, kubectl, helm | binary | AGENTS |
| ami-repo | core | python, git | binary, system | AGENTS |
| ami-transcripts | core | python | binary | AGENTS |
| ami-mail | enterprise | rust, gcc-glibc | binary + submodule | STREAMS |
| ami-chat | enterprise | matrix-commander | binary | STREAMS |
| ami-synadm | enterprise | synadm | binary | STREAMS |
| ami-kcadm | enterprise | keycloak container | container | DATAOPS |
| ami-browser | enterprise | python (playwright) | binary | AGENTS |
| ami-backup | dev | python, gcloud (opt) | binary | DATAOPS |
| ami-restore | dev | python | binary | DATAOPS |
| ami-gcloud | dev (hidden) | gcloud SDK | binary | AGENTS |
| ami-cron | dev | python | binary | AGENTS |
| ami-ssh | infra (hidden) | openssh | system | AGENTS |
| ami-vpn | infra (hidden) | openvpn | system | AGENTS |
| ami-tunnel | infra (hidden) | cloudflared | binary | AGENTS |
| ami-ssl | infra (hidden) | openssl | system | AGENTS |
| ami-docs | docs | pandoc, wkhtmltopdf, texlive | binary | AGENTS |
| ami-claude | agents | claude code (node) | binary | AGENTS |
| ami-gemini | agents | gemini cli (node) | binary | AGENTS |
| ami-qwen | agents | qwen code (node) | binary | AGENTS |

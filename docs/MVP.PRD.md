# vm config factory — mvp prd

## 0. meta

- **doc owner**: alek
- **last updated**: 2025‑07‑24
- **status**: mvp draft v0.1

## 1. core problem

> devops teams need to spin up **one repeatable 2‑vm stack** (grafana + postgres) on existing aws ec2 instances without hand‑rolled playbooks.

## 2. mvp goals / metrics

| id | target             | metric                                                           |
| -- | ------------------ | ---------------------------------------------------------------- |
| g1 | one‑command deploy | `vm-config apply grafana-postgres` provisions both vms in ≤5 min |
| g2 | idempotent rerun   | second run shows 0 tasks changed                                 |
| g3 | minimal modularity | drop‑in custom `monitoring` layer without editing framework      |
| g4 | team adoption      | first internal team uses tool within 2 weeks                     |

## 3. scope (mvp)

### in‑scope

- single template: `grafana-postgres`
- layers: base‑os, docker, application (grafana/postgres), networking (nginx ssl)
- aws ec2 only; existing vm, ubuntu 22.04
- cli commands: `init`, `validate`, `apply`, `list`
- generated artifacts: ansible inventory + playbook
- secret management: ansible‑vault file reference (no cli for vault ops)

### out‑of‑scope

- provisioning vpc / security groups
- auto‑scaling / self‑healing
- multi‑cloud support
- advanced ci/cd integration

### assumptions

- ssh key auth available
- docker required runtime
- outbound internet access

## 4. architecture snapshot

```text
cli (typer)
  → framework (python)
    → template registry
      → layers
        → artifact generators
          → ansible + scripts → ssh → target vms
```

## 5. functional requirements (fr)

| id  | requirement  | acceptance                                                                              |
| --- | ------------ | --------------------------------------------------------------------------------------- |
| fr1 | init project | `vm-config init grafana-postgres --env dev` creates dir tree & config passes validation |
| fr2 | apply config | single command configures both vms end‑to‑end                                           |
| fr3 | rerun safe   | re‑applying on configured vms makes no changes                                          |
| fr4 | add layer    | placing `custom_layers/monitoring.py` then `vm-config layer validate` passes            |

## 6. non‑functional requirements (nfr)

| id   | requirement                                |
| ---- | ------------------------------------------ |
| nfr1 | deploy ≤5 min                              |
| nfr2 | logs to stdout + file with rich formatting |
| nfr3 | python 3.11+ with uv‑managed env only      |
| nfr4 | unit test coverage ≥70 %                   |

## 7. success metrics

- time to first deploy ≤1 day for a new engineer
- mean deploy time ≤5 min in ci measurement
- 0 drift detected over 10 consecutive reruns

## 8. open questions

- **vault ux**: should cli wrap ansible‑vault for secret injection?
- **state tracking**: need local state file, or rely on ansible facts?
- **packaging**: distribute via pypi or internal artifactory?


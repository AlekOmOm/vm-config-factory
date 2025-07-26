# [code-health] service layer refactoring & idempotency improvements (2025-07-26)

Based on a quick scan of the vm‑config factory repository and the work items under docs/issues/, there are a few high‑leverage improvements that would bring the codebase closer to the MVP/PRD targets. These are ranked by impact × effort.

## 1. Move service‑specific layers into a docker_services sub‑package

### Problem: 
The top‑level layers/ directory currently mixes generic building blocks (base_os.py, docker.py, networking.py) with service‑specific application layers (GrafanaLayer, PostgreSQLLayer, PrometheusLayer) that live in layers/application.py. As more services are added this flat structure will become unwieldy and will blur the boundary between generic layers and service‑specific logic. The current LayerRegistry manually imports these classes, making extensibility harder.

### Why it matters: 
A clear modular structure makes it obvious which layers are reusable versus service‑specific. Keeping service‑specific layers under a separate namespace (layers/docker_services/) enables us to auto‑register them and maintain backwards‑compatible imports. This aligns with the PRD goal of template + layer composability and reduces the surface area of the framework. It also matches the documented plan in docs/issues/docker_services.md.

### Proposed change:

- Create layers/docker_services/ with its own __init__.py that imports and registers GrafanaLayer, PostgresqlLayer, and PrometheusLayer using LayerRegistry.register_layer(). 
  - Provide an optional dynamic discovery loop (using pkgutil.iter_modules) to automatically register any new service layer classes found in this package
- Move each service layer from layers/application.py into its own module: layers/docker_services/grafana.py, layers/docker_services/postgresql.py, and layers/docker_services/prometheus.py. Preserve class names, documentation strings, and dependencies.

- In layers/__init__.py re‑export these layers so that both from layers.grafana import GrafanaLayer and from layers.docker_services.grafana import GrafanaLayer continue to work, as illustrated in the issue
GitHub. Update the __all__ list accordingly.

- Update src/vmconfig/registry.py to import from layers/docker_services instead of application.py, or better, delegate registration to the package’s __init__.py. Remove manual registration for service layers once dynamic discovery is in place.

### Acceptance check: 
After refactoring, the following should succeed without code changes:

```python
from layers.grafana import GrafanaLayer
from layers.docker_services.grafana import GrafanaLayer
from vmconfig.framework.layers import LayerRegistry
assert LayerRegistry.get("grafana") is GrafanaLayer
```

Running `vm-config validate` and `vm-config apply --dry-run` on the `grafana-postgres` template should produce the same task order as before (verify via `ansible-playbook --check --diff`) with zero changes on subsequent re‑runs.

### Scope: 
`layers/application.py` → new files under `layers/docker_services/`; `layers/__init__.py`, `layers/docker_services/__init__.py`, `src/vmconfig/registry.py`, and any packaging configuration (e.g. `pyproject.toml` packages directive).


## 2. Split layers/application.py into separate modules and move inline content to templates

### Problem: 
`layers/application.py` contains two large classes (`GrafanaLayer`, `PostgreSQLLayer`) with embedded multi‑line YAML/INI strings for docker‑compose files and configuration files. This makes the file long and hard to maintain. Any change to the service configuration requires editing Python code, and the inline strings lack syntax highlighting and risk indentation issues.

### Why it matters: 
Separating each service into its own module improves readability and cohesion. 
- Moving YAML/INI bodies to Jinja2 templates stored under `templates/grafana-postgres/assets/` (as suggested in `docs/issues/grafana_postgres.md`) enables template reuse and easier editing. 
- Using the template Ansible module rather than copy ensures variables can be substituted cleanly and supports `--diff` for idempotency checks.

### Proposed change:

- Create individual modules for `GrafanaLayer` and `PostgreSQLLayer` in `layers/docker_services/` (see suggestion 1). Each module should implement `generate_ansible_tasks`, `generate_handlers`, and `generate_scripts` as in `application.py`

- Extract the long docker‑compose and configuration content into Jinja2 template files under `templates/grafana-postgres/assets/` (`grafana-docker-compose.yml.j2`, `postgres-docker-compose.yml.j2`, `grafana.ini.j2`, `postgresql.conf.j2`, `pg_hba.conf.j2`, etc.). The templates can reference variables such as `grafana_port` or `postgres_password` directly.

- Replace the copy tasks in `generate_ansible_tasks` with template tasks pointing at these files (e.g. `src: "grafana-docker-compose.yml.j2", dest: f"{root}/docker-compose.yml"`) and add `mode` and `notify` directives as appropriate.

### Acceptance check: 
The service modules should still generate the same Ansible tasks. Running `ansible-playbook --check` on the generated playbook should show no changes after a second run. The codebase should pass ruff, black, isort, mypy, and tests should maintain ≥70% coverage.

### Scope: 
`layers/application.py` → new modules; creation of Jinja2 assets under `templates/grafana-postgres/assets/`; updates to service layer code to use template module instead of inline strings; tests verifying the file move.

## 3. Improve idempotency and explicitness in Ansible tasks

### Problem: 
Many Ansible tasks in the existing layers perform actions unconditionally. 
- For example, adding the Docker GPG key and repository in `layers/docker.py` may always report a change, and fact‑setting tasks (`set_fact`) do not specify `changed_when: false`. 
- Additionally, file operations lack `creates` conditions or force flags, potentially causing unnecessary modifications.

### Why it matters: 
Idempotency is a core MVP requirement: running `vm-config apply` repeatedly should result in zero changes. 
- Unconditional tasks slow down re‑runs, make `--diff` noise, and can introduce subtle side effects. 
- Explicit `changed_when` and `when` clauses help `ansible-lint` pass and aid readability. 
- Adding `creates` to file tasks prevents copying over existing files.

### Proposed change:

- Audit each `generate_ansible_tasks` function and add `changed_when: false` to tasks that only set facts or perform idempotent operations (e.g. `set_fact` and copy tasks that write the same content). This ensures these tasks do not mark the play as changed.

- For tasks that add repositories or keys (e.g. `apt_key`, `apt_repository`), use Ansible’s built‑in idempotency features: ensure `state: present` and add `validate_certs` or `update_cache` only when needed. For example, use `creates: /etc/apt/trusted.gpg.d/docker.gpg` to avoid re‑adding the key.

- Add `when` conditions to tasks that stop/start services only if a change in configuration occurred. For instance, only stop nginx when obtaining SSL certificates if `need_ssl_cert` is true and the service is running.

- Validate the generated playbook using `ansible-playbook --check --diff` to confirm zero changes on a second run; integrate this into CI.

### Acceptance check: 
After these adjustments, run `ansible-lint` against the generated playbook and ensure there are no idempotency warnings. Run `ansible-playbook --check --diff` twice and confirm the second run produces no changes. Ensure existing functionality (e.g. firewall rules) remains unaffected.

### Scope: 
All layer modules (`layers/base_os.py`, `layers/docker.py`, `layers/networking.py`, `layers/prometheus.py`, new service modules) need targeted additions of `changed_when`, `creates`, and `when`. Update tests or create new tests that perform a dry run twice and assert zero tasks report changes on the second run.

## 4. Improve layer discovery and registration

### Problem: 
The current `src/vmconfig/registry.py` hardcodes imports and registers each layer manually, and falls back to dummy classes on import errors. As new service layers are added, maintaining this list becomes error‑prone. Hard‑coded imports also increase the risk of circular dependencies.

### Why it matters: 
Automatic layer discovery reduces the amount of boilerplate needed when adding new layers. It ensures that all valid `ConfigLayer` subclasses are registered once and prevents stale imports. It also simplifies `layers/__init__.py` by removing manual imports.

### Proposed change:

- Move the responsibility of registering service layers into `layers/docker_services/__init__.py` (see suggestion 1). 
  - Use the dynamic discovery loop described in the issue to iterate over modules and register any class that defines a name and a `generate_ansible_tasks` method.

- In `src/vmconfig/registry.py`, remove manual imports of `GrafanaLayer`, `PostgreSQLLayer`, and `PrometheusLayer`. 
  - Instead, import layers once to trigger its import‑time registration side effects. Retain explicit registration for core layers (`BaseOSLayer`, `DockerLayer`, `NetworkingLayer`) to avoid relying on dynamic discovery for framework essentials.

- Provide unit tests to ensure that after importing `vmconfig.registry.initialize_registry()`, all expected layer names are present in `LayerRegistry.registry`.

### Acceptance check: 
New service layer modules added to `layers/docker_services/` should automatically appear in `LayerRegistry.registry` without code changes. 
- Old import paths should continue to work. 
- ruff and mypy should not complain about unused imports or circular dependencies.

### Scope: 
`src/vmconfig/registry.py`, `layers/docker_services/__init__.py`, and associated tests.

## 1. Enhance CLI UX and documentation
### Problem: 
The Typer-based CLI exposes `init`, `validate`, and `apply` commands but could benefit from a more consistent flag interface and richer feedback. 
- For example, `apply` could support `--dry-run` with the same output as a real run, `--diff` to show changes, and logs could be streamed to both stdout and a file for debugging. 
- The quick start guide and PRD mention features that are not yet fully implemented.

### Why it matters: 
A polished CLI improves adoption and reduces operator error. 
- Clear help messages and uniform flag names across commands align with the PRD’s usability goals. 
- Logging to both console and file aids troubleshooting.

### Proposed change:

- Audit the Typer commands (`src/vmconfig/cli/*.py`) to ensure consistent parameters: `--env`, `--dry-run`, `--diff`, etc. 
  - Use rich‑styled output (tables, progress bars) for status reporting. 
  - Validate environment names early and provide actionable error messages.

- Implement `--dry-run` for `apply` that invokes the framework but passes `check=True` to the Ansible runner. 
  - Mirror the exact task ordering and return code of a real run. 
  - Use `--diff` to include diffs when tasks change.

- Write to a log file in `environments/<env>/apply.log` while streaming logs to stdout. 
  - Expose a `--log-file` option for custom paths.

- Update `docs/QUICK_START.md` and the PRD to reflect these commands. 
  - Provide example workflows for adding custom layers.

### Acceptance check: 
Running `vm-config --help` should display consistent help text across subcommands. 
- `vm-config apply --dry-run --diff --env dev` should execute without side effects and show which tasks would change. 
  - Logs should appear in both stdout and the configured log file. 
- All changes should pass `ruff`, `black`, `mypy` and existing tests should still pass.

### Scope: 
`src/vmconfig/cli/*`, documentation files (`README.md`, `docs/QUICK_START.md`), and tests for CLI behavior.

## Quick wins / auto‑PR checklist
If time allows for a small agent PR (≤200 LOC, ≤3 files), the following are simple improvements that can be auto‑applied:

- Add `changed_when: false` to all `set_fact` tasks across layers to suppress unnecessary changes. This typically touches 3–5 files and does not alter behavior. Include an ansible‑lint check to verify no idempotency warnings.

- Refactor `layers/__init__.py` to re‑export service layers from a future `docker_services` package (pre‑work for suggestion 1). This small change (a few import lines) will make both import paths work once the package exists.

- Introduce a simple dynamic layer discovery loop in `layers/docker_services/__init__.py` (just the loop shown in the issue) so that adding new files automatically registers their classes.

---

These improvements are behavior‑preserving, small in scope, and improve modularity and idempotency with minimal risk. 
- They should pass all linting and test gates; the acceptance check is simply that the existing integration tests continue to pass and `ansible-playbook --check` yields no additional changes on a second run.
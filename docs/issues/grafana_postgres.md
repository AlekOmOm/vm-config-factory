Below is a “recipe” to extract the **Grafana** and **PostgreSQL** logic from
the playbook into two dedicated layers, just like we did for *prometheus*.
Nothing in `layers/docker.py` needs to change.

───────────────────────────────────────────────────────────────────────────────
1. File layout
───────────────────────────────────────────────────────────────────────────────
```
layers/
├── base_os.py
├── docker.py
├── networking.py
├── grafana.py          # ← new
└── postgresql.py       # ← new

templates/
└── grafana-postgres/
    ├── template.py
    └── assets/
        ├── grafana-docker-compose.yml.j2
        ├── postgres-docker-compose.yml.j2
        ├── grafana.ini.j2                     # optional
        ├── postgresql.conf.j2
        ├── pg_hba.conf.j2
        └── grafana-nginx.conf.j2              # already present
```

───────────────────────────────────────────────────────────────────────────────
2. New Grafana layer (`layers/grafana.py`)
───────────────────────────────────────────────────────────────────────────────
```python
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class GrafanaLayer(ConfigLayer):
    name = "grafana"
    description = "Deploy Grafana via Docker-Compose"
    dependencies = ["docker"]

    def generate_ansible_tasks(self, vm_cfg):
        root = vm_cfg.get("grafana_root", "/opt/grafana")
        port = vm_cfg.get("grafana_port", 3000)

        return [
            # firewall
            AnsibleTask(
                name="Allow Grafana port",
                module="ufw",
                params={"port": port, "proto": "tcp", "rule": "allow"},
            ),
            # directories
            AnsibleTask(
                name="Create Grafana directories",
                module="file",
                params={
                    "path": f"{root}/{{ item }}",
                    "state": "directory",
                    "owner": "472",
                    "group": "472",
                    "mode": "0755",
                },
                loop=["data", "logs"],
            ),
            # compose + config
            AnsibleTask(
                name="Upload Grafana compose file",
                module="template",
                params={
                    "src": "grafana-docker-compose.yml.j2",
                    "dest": f"{root}/docker-compose.yml",
                    "mode": "0644",
                },
            ),
            # optional grafana.ini
            AnsibleTask(
                name="Upload grafana.ini",
                module="template",
                params={
                    "src": "grafana.ini.j2",
                    "dest": f"{root}/grafana.ini",
                    "mode": "0644",
                },
                when="grafana_custom_ini | default(false)",
            ),
            # start / update stack
            AnsibleTask(
                name="Start Grafana stack",
                module="community.docker.docker_compose_v2",
                params={
                    "project_src": root,
                    "recreate": "auto",
                    "remove_orphans": True,
                    "state": "present",
                },
            ),
            # heath-check
            AnsibleTask(
                name="Wait for Grafana API",
                module="uri",
                params={
                    "url": f"http://localhost:{port}/api/health",
                    "status_code": 200,
                    "method": "GET",
                },
                retries=30,
                delay=2,
            ),
        ]

    def generate_handlers(self):
        # if you want an explicit restart-grafana handler
        return [
            {
                "name": "restart grafana",
                "community.docker.docker_compose_v2": {
                    "project_src": "/opt/grafana",
                    "recreate": "always",
                    "state": "present",
                },
            }
        ]
```

───────────────────────────────────────────────────────────────────────────────
3. New PostgreSQL layer (`layers/postgresql.py`)
───────────────────────────────────────────────────────────────────────────────
```python
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class PostgresqlLayer(ConfigLayer):
    name = "postgresql"
    description = "Deploy PostgreSQL in a container and create users/dbs"
    dependencies = ["docker"]

    def generate_ansible_tasks(self, vm_cfg):
        root = vm_cfg.get("postgres_root", "/opt/postgres")
        port = vm_cfg.get("postgres_port", 5432)

        return [
            # firewall
            AnsibleTask(
                name="Allow PostgreSQL port",
                module="ufw",
                params={"port": port, "proto": "tcp", "rule": "allow"},
            ),
            # dirs
            AnsibleTask(
                name="Create PostgreSQL directories",
                module="file",
                params={
                    "path": f"{root}/{{ item }}",
                    "state": "directory",
                    "mode": "0755",
                },
                loop=["data", "config", "logs"],
            ),
            # config files
            AnsibleTask(
                name="Upload postgresql.conf",
                module="template",
                params={
                    "src": "postgresql.conf.j2",
                    "dest": f"{root}/config/postgresql.conf",
                    "mode": "0644",
                },
            ),
            AnsibleTask(
                name="Upload pg_hba.conf",
                module="template",
                params={
                    "src": "pg_hba.conf.j2",
                    "dest": f"{root}/config/pg_hba.conf",
                    "mode": "0644",
                },
            ),
            # compose
            AnsibleTask(
                name="Upload PostgreSQL compose file",
                module="template",
                params={
                    "src": "postgres-docker-compose.yml.j2",
                    "dest": f"{root}/docker-compose.yml",
                    "mode": "0644",
                },
            ),
            # start container
            AnsibleTask(
                name="Start PostgreSQL stack",
                module="community.docker.docker_compose_v2",
                params={
                    "project_src": root,
                    "recreate": "auto",
                    "remove_orphans": True,
                    "state": "present",
                },
            ),
            # wait until ready
            AnsibleTask(
                name="Wait for PostgreSQL",
                module="postgresql_ping",
                params={
                    "login_host": "localhost",
                    "login_user": "postgres",
                    "login_password": "{{ postgres_password }}",
                    "db": "postgres",
                },
                retries=30,
                delay=2,
            ),
            # create users
            AnsibleTask(
                name="Create application users",
                module="postgresql_user",
                params={
                    "name": "{{ item.name }}",
                    "password": "{{ item.password }}",
                    "login_host": "localhost",
                    "login_user": "postgres",
                    "login_password": "{{ postgres_password }}",
                    "state": "present",
                },
                loop="{{ postgres_users | default([]) }}",
            ),
            # create databases
            AnsibleTask(
                name="Create application databases",
                module="postgresql_db",
                params={
                    "name": "{{ item.db }}",
                    "owner": "{{ item.name }}",
                    "state": "present",
                    "login_host": "localhost",
                    "login_user": "postgres",
                    "login_password": "{{ postgres_password }}",
                },
                loop="{{ postgres_users | default([]) }}",
            ),
        ]

    def generate_handlers(self):
        return [
            {
                "name": "restart postgres",
                "community.docker.docker_compose_v2": {
                    "project_src": "/opt/postgres",
                    "recreate": "always",
                    "state": "present",
                },
            }
        ]
```

Don’t forget to register the layers once at import time:

```python
# __init__.py or inside each layer file
from vmconfig.framework.layers import LayerRegistry
LayerRegistry.register_layer("grafana", GrafanaLayer)
LayerRegistry.register_layer("postgresql", PostgresqlLayer)
```

───────────────────────────────────────────────────────────────────────────────
4. Move Jinja2 assets
───────────────────────────────────────────────────────────────────────────────
Copy the hard-coded strings that were inside the playbook into proper files
under `templates/grafana-postgres/assets/`:

- `grafana-docker-compose.yml.j2`
- `postgres-docker-compose.yml.j2`
- `postgresql.conf.j2`
- `pg_hba.conf.j2`
- keep the existing `grafana-nginx.conf.j2`

The compose templates can use the same variables you had inline, e.g.

```yaml
version: "3.8"
services:
  grafana:
    image: grafana/grafana:{{ grafana_version | default('latest') }}
    ports:
      - "{{ grafana_port }}:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD={{ grafana_admin_password }}
      - GF_DATABASE_TYPE=postgres
      - GF_DATABASE_HOST={{ grafana_database_host }}
      - GF_DATABASE_NAME={{ grafana_database_name }}
      - GF_DATABASE_USER={{ grafana_database_user }}
      - GF_DATABASE_PASSWORD={{ grafana_database_password }}
    volumes:
      - "{{ grafana_root }}/data:/var/lib/grafana"
      - "{{ grafana_root }}/logs:/var/log/grafana"
```

───────────────────────────────────────────────────────────────────────────────
5. Update the template (`templates/grafana-postgres/template.py`)
───────────────────────────────────────────────────────────────────────────────
- Replace `layers=['base-os', 'docker', 'grafana', 'networking']`
  (was already there) – good.
- Ensure the **postgres VM** now uses `layers=['base-os', 'docker','postgresql']`
  (you can drop any in-place tasks you previously kept).

Nothing else changes: the generator now assembles the playbook from the new
layers, each layer contributes its own tasks/handlers, and the generic Docker
layer stays clean and reusable.

───────────────────────────────────────────────────────────────────────────────
6. Run it
───────────────────────────────────────────────────────────────────────────────
```bash
vm-config validate --env dev
vm-config apply    --env dev
```

You should see:

- Docker installed first
- Postgres stack started on the `postgres` VM
- Grafana stack started on the `grafana` VM
- No more monolithic mega-tasks inside the playbook – everything lives in its
  own layer and can be reused by future templates.
Put the *Prometheus stack itself* in its own layer – **not** in
`layers/docker.py`.

Why?

1. `layers/docker.py` is template-agnostic infrastructure code.  
   It makes sure any VM has Docker Engine + Compose installed and running.
   It must stay generic because every template (`grafana-postgres`,
   `prometheus`, future ones …) re-uses it.

2. Prometheus (or Grafana, Loki, Redis …) is **application logic**, not
   infrastructure.  
   It belongs in a dedicated layer that:
   - creates `/opt/prometheus/{data,config,logs}`  
   - copies a `docker-compose.yml` and `prometheus.yml` template  
   - starts / restarts the Compose project  
   - opens port 9090 in the firewall  
   - optionally waits for `/-/ready` to return 200

Recommended file layout

```
layers/
├── docker.py               # installs & configures Docker Engine
├── base_os.py
├── networking.py
└── prometheus.py           # <— new
templates/
└── prometheus/
    ├── template.py         # registers VM + lists 'prometheus' layer
    └── assets/
        ├── docker-compose.yml.j2
        └── prometheus.yml.j2
```

Minimal `layers/prometheus.py`

```python
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class PrometheusLayer(ConfigLayer):
    name = "prometheus"
    description = "Deploy Prometheus + Node-Exporter via Docker Compose"
    dependencies = ["docker"]          # requires Docker Engine first

    def generate_ansible_tasks(self, vm_cfg):
        root = vm_cfg.get("prometheus_root", "/opt/prometheus")
        port = vm_cfg.get("prometheus_port", 9090)

        return [
            # firewall
            AnsibleTask(
                name="Allow Prometheus port",
                module="ufw",
                params={"port": port, "proto": "tcp", "rule": "allow"},
            ),
            # directories
            AnsibleTask(
                name="Create Prometheus directories",
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
                name="Upload prometheus.yml",
                module="template",
                params={
                    "src": "prometheus.yml.j2",
                    "dest": f"{root}/config/prometheus.yml",
                    "mode": "0644",
                },
            ),
            AnsibleTask(
                name="Upload docker-compose file",
                module="template",
                params={
                    "src": "docker-compose.yml.j2",
                    "dest": f"{root}/docker-compose.yml",
                    "mode": "0644",
                },
            ),
            # start / update stack
            AnsibleTask(
                name="Start Prometheus stack",
                module="community.docker.docker_compose_v2",
                params={
                    "project_src": root,
                    "recreate": "auto",
                    "remove_orphans": True,
                    "state": "present",
                },
            ),
            # health-check
            AnsibleTask(
                name="Wait for Prometheus API",
                module="uri",
                params={
                    "url": f"http://localhost:{port}/-/ready",
                    "status_code": 200,
                    "method": "GET",
                },
                retries=30,
                delay=2,
            ),
        ]

    def generate_handlers(self):
        # none for now
        return []
```

Then, inside `templates/prometheus/template.py` list the new layer:

```python
from vmconfig.framework.templates import ServiceTemplate, TemplateVm
from vmconfig.framework.layers import LayerRegistry
from layers.prometheus import PrometheusLayer   # make sure it is imported

LayerRegistry.register_layer("prometheus", PrometheusLayer)

class PrometheusTemplate(ServiceTemplate):
    slug = "prometheus"
    description = "Single-VM Prometheus stack"

    vms = {
        "prometheus": TemplateVm(
            layers=["base-os", "docker", "prometheus", "networking"],
            services=["prometheus", "nginx"],
            vars={
                "prometheus_port": 9090,
                "prometheus_root": "/opt/prometheus",
            },
        )
    }
```

Resulting flow during `vm-config apply`:

1. `base-os` hardens the VM.  
2. `docker` installs the engine.  
3. `prometheus` layer drops the Compose file + config and runs it.  
4. `networking` layer sets up Nginx if you include it.

This keeps the separation of concerns intact and lets every template
compose layers freely without touching the shared `docker.py`.
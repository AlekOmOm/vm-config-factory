from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class PrometheusLayer(ConfigLayer):
    name = "prometheus"
    description = "Deploy Prometheus + Node-Exporter via Docker Compose"
    dependencies = ["docker"]

    def generate_ansible_tasks(self, vm_cfg):
        root = vm_cfg.get("prometheus_root", "/opt/prometheus")
        port = vm_cfg.get("prometheus_port", 9090)

        return [
            AnsibleTask(
                name="Allow Prometheus port",
                module="ufw",
                params={"port": port, "proto": "tcp", "rule": "allow"},
            ),
            AnsibleTask(
                name="Set prometheus directories",
                module="set_fact",
                params={
                    "prometheus_dirs": [
                        f"{root}/data",
                        f"{root}/config", 
                        f"{root}/logs"
                    ]
                }
            ),
            AnsibleTask(
                name="Create prometheus directories",
                module="file",
                params={
                    "path": "{{ item }}",
                    "state": "directory",
                    "mode": "0755",
                    "owner": "65534",
                    "group": "65534"
                },
                loop="{{ prometheus_dirs }}"
            ),
            AnsibleTask(
                name="Create prometheus.yml config",
                module="copy",
                params={
                    "content": '''global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:{{ prometheus_port | default(9090) }}']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']''',
                    "dest": f"{root}/config/prometheus.yml",
                    "mode": "0644",
                },
            ),
            AnsibleTask(
                name="Create docker-compose file",
                module="copy",
                params={
                    "content": '''version: '3.8'

services:
  prometheus:
    image: prom/prometheus:{{ prometheus_version | default('latest') }}
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "{{ prometheus_port | default(9090) }}:9090"
    volumes:
      - {{ prometheus_root | default('/opt/prometheus') }}/data:/prometheus
      - {{ prometheus_root | default('/opt/prometheus') }}/config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - {{ prometheus_root | default('/opt/prometheus') }}/logs:/var/log/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=15d'
      - '--web.enable-lifecycle'
    networks:
      - prometheus_network

  node-exporter:
    image: prom/node-exporter:{{ node_exporter_version | default('latest') }}
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - prometheus_network

networks:
  prometheus_network:
    driver: bridge''',
                    "dest": f"{root}/docker-compose.yml",
                    "mode": "0644",
                },
            ),
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
        return [] 
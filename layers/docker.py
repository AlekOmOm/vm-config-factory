"""Docker configuration layer"""
from typing import Dict, List, Any
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class DockerLayer(ConfigLayer):
    """Docker Engine and Docker Compose installation"""
    
    name = "docker"
    description = "Docker Engine, Docker Compose, and container runtime"
    dependencies = ["base-os"]
    
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate Docker installation tasks"""
        tasks = [
            AnsibleTask(
                name="Install prerequisites for Docker",
                module="apt",
                params={
                    "name": [
                        "apt-transport-https", "ca-certificates", 
                        "curl", "gnupg", "lsb-release"
                    ],
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Add Docker GPG key",
                module="apt_key",
                params={
                    "url": "https://download.docker.com/linux/ubuntu/gpg",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Add Docker repository",
                module="apt_repository",
                params={
                    "repo": "deb https://download.docker.com/linux/ubuntu {{ ansible_distribution_release }} stable",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Install Docker Engine",
                module="apt",
                params={
                    "name": ["docker-ce", "docker-ce-cli", "containerd.io", "docker-compose-plugin"],
                    "state": "present",
                    "update_cache": True
                }
            ),
            AnsibleTask(
                name="Start and enable Docker service",
                module="service",
                params={
                    "name": "docker",
                    "state": "started",
                    "enabled": True
                }
            ),
            AnsibleTask(
                name="Add user to docker group",
                module="user",
                params={
                    "name": "{{ ansible_user }}",
                    "groups": "docker",
                    "append": True
                }
            ),
            AnsibleTask(
                name="Configure Docker daemon",
                module="copy",
                params={
                    "content": '''{{ docker_daemon_config | to_nice_json }}''',
                    "dest": "/etc/docker/daemon.json",
                    "mode": "0644"
                },
                notify="restart docker"
            ),
            AnsibleTask(
                name="Set Docker daemon configuration",
                module="set_fact",
                params={
                    "docker_daemon_config": {
                        "log-driver": "json-file",
                        "log-opts": {
                            "max-size": "10m",
                            "max-file": "3"
                        },
                        "storage-driver": "overlay2"
                    }
                }
            ),
            AnsibleTask(
                name="Create docker compose directory",
                module="file",
                params={
                    "path": "/opt/docker-compose",
                    "state": "directory",
                    "mode": "0755"
                }
            )
        ]
        
        return tasks
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate handlers for Docker layer"""
        return [
            {
                "name": "restart docker",
                "service": {
                    "name": "docker",
                    "state": "restarted"
                }
            }
        ]
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate Docker management scripts"""
        return {
            "docker-health.sh": """#!/bin/bash
# Docker health check script
echo "=== Docker Status ==="
systemctl status docker --no-pager
echo ""
echo "=== Docker Version ==="
docker --version
docker compose version
echo ""
echo "=== Running Containers ==="
docker ps
echo ""
echo "=== Docker Images ==="
docker images
echo ""
echo "=== Docker System Info ==="
docker system df
""",
            "docker-cleanup.sh": """#!/bin/bash
# Docker cleanup script
echo "Cleaning up Docker resources..."
docker system prune -f
docker volume prune -f
docker network prune -f
echo "Docker cleanup completed"
""",
            "docker-logs.sh": """#!/bin/bash
# Docker logs script
if [ -z "$1" ]; then
    echo "Usage: $0 <container_name>"
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

docker logs -f --tail=100 "$1"
"""
        }

"""Base OS configuration layer"""
from typing import Dict, List, Any
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class BaseOSLayer(ConfigLayer):
    """Base operating system configuration"""
    
    name = "base-os"
    description = "User management, SSH hardening, basic security"
    dependencies = []
    
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate base OS configuration tasks"""
        tasks = [
            AnsibleTask(
                name="Update apt cache",
                module="apt",
                params={"update_cache": True, "cache_valid_time": 3600}
            ),
            AnsibleTask(
                name="Install essential packages",
                module="apt",
                params={
                    "name": [
                        "curl", "wget", "unzip", "git", "htop", 
                        "vim", "ufw", "fail2ban", "certbot"
                    ],
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Set SSH hardening parameters",
                module="set_fact",
                params={
                    "ssh_hardening": [
                        {"key": "PermitRootLogin", "value": "no"},
                        {"key": "PasswordAuthentication", "value": "no"},
                        {"key": "X11Forwarding", "value": "no"},
                        {"key": "MaxAuthTries", "value": "3"}
                    ]
                }
            ),
            AnsibleTask(
                name="Apply SSH hardening",
                module="lineinfile",
                params={
                    "path": "/etc/ssh/sshd_config",
                    "regexp": "^#?{{ item.key }}",
                    "line": "{{ item.key }} {{ item.value }}",
                    "state": "present"
                },
                loop="{{ ssh_hardening }}",
                notify="restart ssh"
            ),
            AnsibleTask(
                name="Configure UFW firewall",
                module="ufw",
                params={
                    "rule": "allow",
                    "port": "22",
                    "proto": "tcp"
                }
            ),
            AnsibleTask(
                name="Enable UFW",
                module="ufw",
                params={"state": "enabled"}
            ),
            AnsibleTask(
                name="Configure fail2ban",
                module="service",
                params={
                    "name": "fail2ban",
                    "state": "started",
                    "enabled": True
                }
            )
        ]
        
        return tasks
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate handlers for base OS layer"""
        return [
            {
                "name": "restart ssh",
                "service": {
                    "name": "ssh",
                    "state": "restarted"
                }
            }
        ]
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate operational scripts"""
        return {
            "system-info.sh": """#!/bin/bash
# System information script
echo "=== System Information ==="
uname -a
echo ""
echo "=== Memory Usage ==="
free -h
echo ""
echo "=== Disk Usage ==="
df -h
echo ""
echo "=== Active Services ==="
systemctl list-units --type=service --state=active
""",
            "security-check.sh": """#!/bin/bash
# Security check script
echo "=== SSH Configuration ==="
grep -E "(PermitRootLogin|PasswordAuthentication)" /etc/ssh/sshd_config
echo ""
echo "=== Firewall Status ==="
ufw status verbose
echo ""
echo "=== Fail2ban Status ==="
fail2ban-client status
"""
        }

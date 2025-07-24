"""Networking configuration layer"""
from typing import Dict, List, Any
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class NetworkingLayer(ConfigLayer):
    """Nginx reverse proxy and SSL configuration"""
    
    name = "networking"
    description = "Nginx reverse proxy, SSL certificates, and network security"
    dependencies = ["base-os"]
    
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate networking configuration tasks"""
        tasks = [
            AnsibleTask(
                name="Install Nginx",
                module="apt",
                params={
                    "name": "nginx",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Start and enable Nginx",
                module="service",
                params={
                    "name": "nginx",
                    "state": "started",
                    "enabled": True
                }
            ),
            AnsibleTask(
                name="Remove default Nginx site",
                module="file",
                params={
                    "path": "/etc/nginx/sites-enabled/default",
                    "state": "absent"
                },
                notify="reload nginx"
            ),
            AnsibleTask(
                name="Create Nginx configuration directory",
                module="file",
                params={
                    "path": "/etc/nginx/sites-available",
                    "state": "directory",
                    "mode": "0755"
                }
            ),
            AnsibleTask(
                name="Configure Nginx proxy settings",
                module="copy",
                params={
                    "content": '''# Proxy settings
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# Timeouts
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;

# Buffer settings
proxy_buffering on;
proxy_buffer_size 8k;
proxy_buffers 8 8k;
''',
                    "dest": "/etc/nginx/conf.d/proxy.conf",
                    "mode": "0644"
                },
                notify="reload nginx"
            ),
            AnsibleTask(
                name="Configure SSL parameters",
                module="copy",
                params={
                    "content": '''# SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;

# SSL session cache
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# OCSP stapling
ssl_stapling on;
ssl_stapling_verify on;

# Security headers
add_header Strict-Transport-Security "max-age=63072000" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
''',
                    "dest": "/etc/nginx/conf.d/ssl.conf",
                    "mode": "0644"
                },
                notify="reload nginx"
            ),
            AnsibleTask(
                name="Allow HTTP traffic through firewall",
                module="ufw",
                params={
                    "rule": "allow",
                    "port": "80",
                    "proto": "tcp"
                }
            ),
            AnsibleTask(
                name="Allow HTTPS traffic through firewall",
                module="ufw",
                params={
                    "rule": "allow",
                    "port": "443",
                    "proto": "tcp"
                }
            ),
            AnsibleTask(
                name="Test Nginx configuration",
                module="command",
                params={"cmd": "nginx -t"},
                notify="reload nginx"
            )
        ]
        
        return tasks
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate handlers for networking layer"""
        return [
            {
                "name": "reload nginx",
                "service": {
                    "name": "nginx",
                    "state": "reloaded"
                }
            },
            {
                "name": "restart nginx",
                "service": {
                    "name": "nginx",
                    "state": "restarted"
                }
            }
        ]
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate networking management scripts"""
        return {
            "nginx-status.sh": """#!/bin/bash
# Nginx status script
echo "=== Nginx Status ==="
systemctl status nginx --no-pager
echo ""
echo "=== Nginx Configuration Test ==="
nginx -t
echo ""
echo "=== Active Connections ==="
ss -tulpn | grep :80
ss -tulpn | grep :443
echo ""
echo "=== Nginx Access Logs (last 10 lines) ==="
tail -10 /var/log/nginx/access.log
""",
            "ssl-check.sh": """#!/bin/bash
# SSL certificate check script
if [ -z "$1" ]; then
    echo "Usage: $0 <domain>"
    exit 1
fi

DOMAIN=$1
echo "=== SSL Certificate Check for $DOMAIN ==="
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates
echo ""
echo "=== Certificate Details ==="
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -subject -issuer
""",
            "nginx-reload.sh": """#!/bin/bash
# Nginx reload script
echo "Testing Nginx configuration..."
if nginx -t; then
    echo "Configuration test passed. Reloading Nginx..."
    systemctl reload nginx
    echo "Nginx reloaded successfully"
else
    echo "Configuration test failed. Not reloading."
    exit 1
fi
"""
        }

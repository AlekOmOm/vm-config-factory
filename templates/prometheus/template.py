from pathlib import Path
from typing import Dict, Any, List
from vmconfig.framework.templates import ServiceTemplate, VMConfig, ValidationResult, Artifact

class PrometheusTemplate(ServiceTemplate):
    name = "prometheus"
    description = "Single-VM Prometheus stack"
    
    def __init__(self):
        super().__init__()
        self.vms = {
            'prometheus': VMConfig(
                layers=['base-os', 'docker', 'prometheus', 'networking'],
                services=['prometheus', 'nginx'],
                vars={
                    'prometheus_port': 9090,
                    'prometheus_root': '/opt/prometheus',
                }
            )
        }
    
    def generate_initial_config(self, environment: str) -> Dict[str, Any]:
        is_dev = environment in ['dev', 'local', 'test']
        default_domain = 'localhost' if is_dev else 'prometheus.example.com'
        
        return {
            'template': self.name,
            'metadata': {
                'description': f'{self.description} - {environment} environment',
                'owner': 'platform-team',
                'environment': environment
            },
            'vms': {
                'prometheus': {
                    'host': '10.0.1.10',
                    'ansible_user': 'ubuntu',
                    'vars': {
                        'prometheus_port': 9090,
                        'prometheus_root': '/opt/prometheus',
                        'prometheus_domain': default_domain,
                        'nginx_use_ssl': True,
                        'nginx_ssl_email': 'admin@example.com'
                    }
                }
            },
            'secrets': {
                'vault_file': f'vault-{environment}.yml',
                'description': 'Ansible vault file containing sensitive variables'
            },
            'validation': {
                'connectivity_checks': True,
                'port_availability': [9090, 80, 443],
                'ssl_cert_expiry': 30
            }
        }
    
    def validate_environment(self, env_config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        vms_config = env_config.get('vms', {})
        
        if 'prometheus' in vms_config:
            prometheus_vars = vms_config['prometheus'].get('vars', {})
            
            prometheus_port = prometheus_vars.get('prometheus_port')
            if prometheus_port and (prometheus_port < 1024 or prometheus_port > 65535):
                errors.append("prometheus_port must be between 1024 and 65535")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def generate_artifacts(self, env_config: Dict[str, Any], output_dir: Path) -> List[Artifact]:
        return []
    
    def generate_initial_assets(self, output_dir: Path) -> None:
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Create example vault file
        vault_example = assets_dir / "vault-example.yml"
        with vault_example.open('w') as f:
            f.write("""# Example vault file - encrypt with: ansible-vault encrypt vault-{env}.yml
vault:
  prometheus:
    # Add any sensitive configuration here if needed
    admin_password: "secure_admin_password_here"
""")
        
        # Create templates directory and Nginx configuration for Prometheus
        templates_dir = output_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        
        nginx_config = templates_dir / "prometheus-nginx.conf.j2"
        with nginx_config.open('w') as f:
            f.write("""# Nginx configuration for Prometheus
# Context-aware configuration that detects AWS domains and dev environments

{% set is_aws_domain = 'amazonaws.com' in prometheus_domain %}
{% set use_ssl = nginx_use_ssl and not is_aws_domain %}

# HTTP server block
server {
    listen 80{% if not use_ssl %} default_server{% endif %};
    server_name {{ prometheus_domain }};
    
{% if use_ssl %}
    # Production with custom domain - redirect to HTTPS
    return 301 https://$server_name$request_uri;
{% else %}
    # Development or AWS domain - serve directly over HTTP
    location / {
        proxy_pass http://localhost:{{ prometheus_port | default(9090) }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Prometheus-specific headers
        proxy_set_header Accept-Encoding "";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }
{% endif %}
}

{% if use_ssl %}
# HTTPS server block (only for custom domains with SSL)
server {
    listen 443 ssl http2;
    server_name {{ prometheus_domain }};
    
    # SSL certificate configuration (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/{{ prometheus_domain }}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{ prometheus_domain }}/privkey.pem;
    
    # Include SSL parameters from networking layer
    include /etc/nginx/conf.d/ssl.conf;
    
    # Proxy to Prometheus
    location / {
        proxy_pass http://localhost:{{ prometheus_port | default(9090) }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Prometheus-specific headers
        proxy_set_header Accept-Encoding "";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }
}
{% endif %}

# Configuration info as comment
# Domain: {{ prometheus_domain }}
# SSL Enabled: {{ use_ssl }}
# AWS Domain: {{ is_aws_domain }}
# Environment: Detected based on nginx_use_ssl variable
""")
        
        # Create deployment guide
        guide = assets_dir / "deployment-guide.md"
        with guide.open('w') as f:
            f.write("""# Prometheus Deployment Guide

## Prerequisites

1. Ubuntu 22.04 VM with SSH access
2. Ansible installed on control machine

## SSL Configuration (Context-Aware)

This template automatically detects your domain type and configures SSL appropriately:

### AWS Domains (*.amazonaws.com)
- **Automatically configured for HTTP-only**
- No SSL certificates needed (AWS owns the domain)
- Access via: `http://your-ec2-instance.amazonaws.com`
- Perfect for development and testing

### Custom Domains (yourdomain.com)
- **Automatically configured for HTTPS with Let's Encrypt**
- SSL certificates obtained and renewed automatically
- Access via: `https://prometheus.yourdomain.com`
- Requires DNS pointing to your server

## Deployment Steps

1. **Initialize project:**
   ```bash
   vm-config init prometheus --env prod --output ./prometheus-prod
   cd prometheus-prod
   ```

2. **Configure environment:**
   - Edit `environments/prod/config.yml` with your VM details
   - Set `prometheus_domain` for your domain
   - Encrypt vault: `ansible-vault encrypt vault-prod.yml`

3. **Validate configuration:**
   ```bash
   vm-config validate --env prod
   ```

4. **Deploy:**
   ```bash
   vm-config apply --env prod
   ```

## Post-Deployment Access

### AWS Domain Setup
- Prometheus: `http://your-ec2-instance.amazonaws.com`
- Node Exporter: `http://your-ec2-instance.amazonaws.com:9100`

### Custom Domain Setup  
- Prometheus: `https://prometheus.yourdomain.com`
- SSL certificates automatically obtained
- HTTP redirects to HTTPS

## Default Ports

- Prometheus: 9090
- Node Exporter: 9100
- Nginx: 80, 443

## Monitoring Targets

The default configuration monitors:
- Prometheus itself
- Node Exporter (system metrics)
- Local host metrics

## Troubleshooting

### General Issues
- Check container status: `docker ps`
- View logs: `docker logs prometheus` or `docker logs node-exporter`

### SSL Issues (Custom Domains Only)
- Check certificate status: `certbot certificates`
- Test SSL: `openssl s_client -connect yourdomain.com:443`

### Log Locations
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Prometheus: `docker logs prometheus`
- Node Exporter: `docker logs node-exporter`
""") 
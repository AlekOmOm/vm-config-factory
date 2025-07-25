"""Grafana + PostgreSQL template"""
from pathlib import Path
from typing import Dict, Any, List
from vmconfig.framework.templates import ServiceTemplate, VMConfig, ValidationResult, Artifact

class GrafanaPostgresTemplate(ServiceTemplate):
    """Grafana + PostgreSQL on separate VMs"""
    
    name = "grafana-postgres"
    description = "Grafana monitoring platform with PostgreSQL database on separate VMs"
    
    def __init__(self):
        super().__init__()
        self.vms = {
            'grafana': VMConfig(
                layers=['base-os', 'docker', 'grafana', 'networking'],
                services=['grafana', 'nginx'],
                dependencies=['postgres']
            ),
            'postgres': VMConfig(
                layers=['base-os', 'docker', 'postgresql'],
                services=['postgresql']
            )
        }
    
    def generate_initial_config(self, environment: str) -> Dict[str, Any]:
        """Generate initial environment configuration"""
        is_dev = environment in ['dev', 'local', 'test']
        
        # Default domain suggestion based on environment
        default_domain = 'localhost' if is_dev else 'grafana.example.com'
        
        return {
            'template': self.name,
            'metadata': {
                'description': f'{self.description} - {environment} environment',
                'owner': 'platform-team',
                'environment': environment
            },
            'vms': {
                'grafana': {
                    'host': '10.0.1.10',  # Replace with actual IP
                    'ansible_user': 'ubuntu',
                    'vars': {
                        'grafana_port': 3000,
                        'grafana_admin_user': 'admin',
                        'grafana_admin_password': '{{vault.grafana.admin_password}}',
                        'grafana_database_host': '{{vms.postgres.host}}',
                        'grafana_database_name': 'grafana',
                        'grafana_database_user': '{{vault.postgres.grafana_user}}',
                        'grafana_database_password': '{{vault.postgres.grafana_password}}',
                        'grafana_domain': default_domain,
                        'nginx_use_ssl': True,  # Default to true, will be auto-detected based on domain
                        'nginx_ssl_email': 'admin@example.com'
                    }
                },
                'postgres': {
                    'host': '10.0.1.11',  # Replace with actual IP
                    'ansible_user': 'ubuntu', 
                    'vars': {
                        'postgres_port': 5432,
                        'postgres_password': '{{vault.postgres.admin_password}}',
                        'postgres_default_db': 'postgres',
                        'postgres_databases': ['grafana'],
                        'postgres_users': [
                            {
                                'name': '{{vault.postgres.grafana_user}}',
                                'password': '{{vault.postgres.grafana_password}}',
                                'db': 'grafana'
                            }
                        ]
                    }
                }
            },
            'secrets': {
                'vault_file': f'vault-{environment}.yml',
                'description': 'Ansible vault file containing sensitive variables'
            },
            'validation': {
                'connectivity_checks': True,
                'port_availability': [3000, 5432, 80, 443],  # Include 443 by default, will be filtered at runtime
                'ssl_cert_expiry': 30
            }
        }
    
    def validate_environment(self, env_config: Dict[str, Any]) -> ValidationResult:
        """Validate environment configuration"""
        errors = []
        warnings = []
        
        vms_config = env_config.get('vms', {})
        
        # Validate Grafana VM configuration
        if 'grafana' in vms_config:
            grafana_vars = vms_config['grafana'].get('vars', {})
            
            if not grafana_vars.get('grafana_admin_password'):
                errors.append("Missing grafana_admin_password in grafana VM vars")
            
            if not grafana_vars.get('grafana_database_host'):
                errors.append("Missing grafana_database_host in grafana VM vars")
            
            # Check if database host references postgres VM
            db_host = grafana_vars.get('grafana_database_host', '')
            if 'postgres' in vms_config and '{{vms.postgres.host}}' not in db_host:
                warnings.append("grafana_database_host should reference postgres VM host")
        
        # Validate PostgreSQL VM configuration
        if 'postgres' in vms_config:
            postgres_vars = vms_config['postgres'].get('vars', {})
            
            if not postgres_vars.get('postgres_password'):
                errors.append("Missing postgres_password in postgres VM vars")
            
            databases = postgres_vars.get('postgres_databases', [])
            if 'grafana' not in databases:
                warnings.append("grafana database not found in postgres_databases list")
        
        # Validate connectivity between VMs
        if 'grafana' in vms_config and 'postgres' in vms_config:
            grafana_host = vms_config['grafana'].get('host')
            postgres_host = vms_config['postgres'].get('host')
            
            if grafana_host and postgres_host:
                # Basic network validation (same subnet recommended)
                import ipaddress
                try:
                    grafana_ip = ipaddress.ip_address(grafana_host)
                    postgres_ip = ipaddress.ip_address(postgres_host)
                    
                    # Check if IPs are in same private network range
                    if not (grafana_ip.is_private and postgres_ip.is_private):
                        warnings.append("VMs should use private IP addresses for security")
                        
                except ValueError:
                    warnings.append("Invalid IP addresses provided for VMs")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def generate_artifacts(self, env_config: Dict[str, Any], output_dir: Path) -> List[Artifact]:
        """Generate deployment artifacts"""
        # This will be handled by the AnsibleGenerator
        # Template-specific customizations can be added here
        return []
    
    def generate_initial_assets(self, output_dir: Path) -> None:
        """Generate initial template assets"""
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Create example vault file
        vault_example = assets_dir / "vault-example.yml"
        with vault_example.open('w') as f:
            f.write("""# Example vault file - encrypt with: ansible-vault encrypt vault-{env}.yml
vault:
  grafana:
    admin_password: "secure_admin_password_here"
  postgres:
    admin_password: "secure_postgres_password_here"
    grafana_user: "grafana_user"
    grafana_password: "secure_grafana_db_password_here"
""")
        
        # Create Nginx configuration template for Grafana
        templates_dir = output_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        
        nginx_config = templates_dir / "grafana-nginx.conf.j2"
        with nginx_config.open('w') as f:
            f.write("""# Context-aware Nginx configuration for Grafana
# This template detects AWS domains and dev environments to configure appropriate SSL settings

{% set is_aws_domain = 'amazonaws.com' in grafana_domain %}
{% set use_ssl = nginx_use_ssl and not is_aws_domain %}

# HTTP server block
server {
    listen 80{% if not use_ssl %} default_server{% endif %};
    server_name {{ grafana_domain }};
    
{% if use_ssl %}
    # Production with custom domain - redirect to HTTPS
    return 301 https://$server_name$request_uri;
{% else %}
    # Development or AWS domain - serve directly over HTTP
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for live updates
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
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
    server_name {{ grafana_domain }};
    
    # SSL certificate configuration (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/{{ grafana_domain }}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{ grafana_domain }}/privkey.pem;
    
    # Include SSL parameters from networking layer
    include /etc/nginx/conf.d/ssl.conf;
    
    # Proxy to Grafana
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for live updates
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
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
# Domain: {{ grafana_domain }}
# SSL Enabled: {{ use_ssl }}
# AWS Domain: {{ is_aws_domain }}
# Environment: Detected based on nginx_use_ssl variable
""")
        
        # Create deployment guide
        guide = assets_dir / "deployment-guide.md"
        with guide.open('w') as f:
            f.write("""# Grafana-PostgreSQL Deployment Guide

## Prerequisites

1. Two Ubuntu 22.04 VMs with SSH access
2. VMs should be in the same network for database connectivity
3. Ansible installed on control machine

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
- Access via: `https://grafana.yourdomain.com`
- Requires DNS pointing to your server

### Development Environments
- When environment is 'dev', 'local', or 'test': **HTTP-only by default**
- Override by setting `nginx_use_ssl: true` in config

## Deployment Steps

1. **Initialize project:**
   ```bash
   vm-config init grafana-postgres --env prod --output ./grafana-prod
   cd grafana-prod
   ```

2. **Configure environment:**
   - Edit `environments/prod/config.yml` with your VM details:
     ```yaml
     grafana_domain: "your-domain.com"     # For custom domain with SSL
     # OR
     grafana_domain: "ec2-xxx.amazonaws.com"  # For AWS domain (HTTP-only)
     
     nginx_use_ssl: true                   # Auto-detected, override if needed
     nginx_ssl_email: "admin@your-domain.com"  # For Let's Encrypt notifications
     ```
   - Copy `assets/vault-example.yml` to `vault-prod.yml`
   - Set secure passwords in vault file
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
- Grafana: `http://your-ec2-instance.amazonaws.com`
- Default login: admin / (password from vault)
- No SSL setup required

### Custom Domain Setup
- Grafana: `https://grafana.yourdomain.com`
- SSL certificates automatically obtained
- HTTP redirects to HTTPS
- Default login: admin / (password from vault)

## Configuration Examples

### Development with AWS Instance
```yaml
environment: dev
grafana_domain: "ec2-13-60-190-242.eu-north-1.compute.amazonaws.com"
nginx_use_ssl: false  # Auto-detected as false
```

### Production with Custom Domain
```yaml
environment: prod
grafana_domain: "grafana.mycompany.com"
nginx_use_ssl: true   # Auto-detected as true
nginx_ssl_email: "admin@mycompany.com"
```

### Development Override (Force SSL)
```yaml
environment: dev
grafana_domain: "dev.mycompany.com"
nginx_use_ssl: true   # Override default dev behavior
nginx_ssl_email: "dev@mycompany.com"
```

## Troubleshooting

### General Issues
- Check container status: `docker ps`
- View logs: `docker logs grafana` or `docker logs postgres`
- Test connectivity: `telnet postgres-vm-ip 5432`

### SSL Issues (Custom Domains Only)
- Check certificate status: `certbot certificates`
- Test SSL: `openssl s_client -connect yourdomain.com:443`
- Renew manually: `certbot renew`
- Check nginx config: `nginx -t`

### AWS Domain Issues
- Ensure security groups allow port 80
- Check if EC2 instance has public IP
- Verify nginx is running: `systemctl status nginx`

### Log Locations
- Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Let's Encrypt: `/var/log/letsencrypt/letsencrypt.log`
- Grafana: `docker logs grafana`

## Security Notes

- AWS domains use HTTP-only by design (AWS manages TLS termination)
- Custom domains automatically get HTTPS with proper certificates
- All configurations include security headers when SSL is enabled
- Firewall rules are automatically configured for required ports
""")

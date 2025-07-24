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
                        'grafana_domain': 'grafana.example.com'
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
                'port_availability': [3000, 5432, 80, 443],
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
        nginx_config = assets_dir / "grafana-nginx.conf"
        with nginx_config.open('w') as f:
            f.write("""# Nginx configuration for Grafana
server {
    listen 80;
    server_name {{ grafana_domain }};
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name {{ grafana_domain }};
    
    # SSL certificate configuration
    ssl_certificate /etc/letsencrypt/live/{{ grafana_domain }}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{ grafana_domain }}/privkey.pem;
    
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
}
""")
        
        # Create deployment guide
        guide = assets_dir / "deployment-guide.md"
        with guide.open('w') as f:
            f.write("""# Grafana-PostgreSQL Deployment Guide

## Prerequisites

1. Two Ubuntu 22.04 VMs with SSH access
2. VMs should be in the same network for database connectivity
3. Ansible installed on control machine

## Deployment Steps

1. **Initialize project:**
   ```bash
   vm-config init grafana-postgres --env prod --output ./grafana-prod
   cd grafana-prod
   ```

2. **Configure environment:**
   - Edit `environments/prod/config.yml` with your VM IPs
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

## Post-Deployment

- Grafana will be available at: http://your-grafana-vm:3000
- Default login: admin / (password from vault)
- PostgreSQL accessible from Grafana VM on port 5432

## Troubleshooting

- Check container status: `docker ps`
- View logs: `docker logs grafana` or `docker logs postgres`
- Test connectivity: `telnet postgres-vm-ip 5432`
""")

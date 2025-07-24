# VM Config Factory - Quick Start Guide

## Installation

### Prerequisites
- Python 3.11+
- `uv` package manager
- SSH access to target Ubuntu 22.04 VMs
- Ansible installed locally

### Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install VM Config Factory
```bash
# From project directory
cd vm-config-factory
uv sync
uv pip install -e .
```

### Verify Installation
```bash
vm-config --help
vm-config list templates
```

## Quick Start - Deploy Grafana + PostgreSQL

### 1. Initialize Project
```bash
vm-config init grafana-postgres --env production --output ./grafana-prod
cd grafana-prod
```

### 2. Configure Your VMs
Edit `environments/production/config.yml`:
```yaml
vms:
  grafana:
    host: "your-grafana-vm-ip"    # Replace with actual IP
    ansible_user: ubuntu
  postgres:
    host: "your-postgres-vm-ip"   # Replace with actual IP
    ansible_user: ubuntu
```

### 3. Setup Secrets
```bash
# Copy vault example
cp assets/vault-example.yml vault-production.yml

# Edit vault file with secure passwords
vim vault-production.yml

# Encrypt vault file
ansible-vault encrypt vault-production.yml
```

### 4. Validate Configuration
```bash
vm-config validate --env production
```

### 5. Deploy
```bash
# Dry run first
vm-config apply --env production --dry-run

# Deploy for real
vm-config apply --env production
```

### 6. Access Grafana
- URL: `http://your-grafana-vm-ip:3000`
- Username: `admin`
- Password: (from your vault file)

## Custom Layer Development

### Create Custom Layer
```bash
vm-config layer create monitoring --output ./custom_layers
```

### Validate Custom Layer
```bash
vm-config layer validate ./custom_layers/monitoring.py
```

### Integrate Custom Layer
1. Edit layer file with your logic
2. Add layer to template or create new template
3. Test with validation

## Common Commands

```bash
# List available templates and layers
vm-config list templates
vm-config list layers

# Initialize different environments
vm-config init grafana-postgres --env dev
vm-config init grafana-postgres --env staging

# Apply to specific VM only
vm-config apply --env prod --vm grafana

# Verbose logging
vm-config apply --env prod --verbose

# Save logs to file
vm-config apply --env prod --log-file deployment.log
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Verify VM IP addresses
   - Check SSH key authentication
   - Ensure firewall allows SSH (port 22)

2. **Ansible Command Not Found**
   ```bash
   pip install ansible
   ```

3. **Permission Denied**
   - Verify `ansible_user` has sudo access
   - Check SSH key permissions (600)

4. **Configuration Validation Failed**
   - Check YAML syntax
   - Verify all required fields present
   - Review vault variable references

### Debug Mode
```bash
vm-config apply --env prod --verbose --log-file debug.log
```

### Get Help
```bash
vm-config --help
vm-config apply --help
vm-config layer --help
```

## Next Steps

- Review generated Ansible playbooks in `environments/`
- Customize layer configurations for your needs
- Set up CI/CD integration
- Create additional templates for other services

For detailed documentation, see the `/docs` directory.

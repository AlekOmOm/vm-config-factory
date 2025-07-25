# Environments Directory

This directory contains environment-specific configurations for your VM deployments. Each subdirectory represents a different environment (dev, staging, production, etc.).

## Structure

```
environments/
├── example/                    # Example environment configuration
│   ├── config.yml             # Main configuration file
│   └── vault-example.yml      # Example vault file (unencrypted)
├── dev/                       # Development environment (created by init)
├── staging/                   # Staging environment (created by init) 
└── production/                # Production environment (created by init)
```

## Creating New Environments

Use the `vm-config init` command to create new environment configurations:

```bash
# Create development environment
vm-config init grafana-postgres --env dev --output ./

# Create production environment  
vm-config init grafana-postgres --env production --output ./
```

This will create:
- `environments/{env}/config.yml` - Main configuration file
- `assets/vault-example.yml` - Template for vault secrets

## Configuration Files

### config.yml
Main configuration file containing:
- VM definitions (hosts, users, variables)
- Template specification
- Validation settings
- Metadata

### vault-{env}.yml
Ansible vault file containing sensitive variables:
- Database passwords
- Admin credentials
- API keys
- SSL certificates

**Always encrypt vault files before committing:**
```bash
ansible-vault encrypt environments/production/vault-production.yml
```

## Generated Files

When you run `vm-config apply`, additional files are generated:
- `inventory.yml` - Ansible inventory
- `playbook.yml` - Ansible playbook
- `group_vars/` - Variable files for each VM
- `scripts/` - Operational scripts

## Example Usage

```bash
# Initialize new environment
vm-config init grafana-postgres --env prod --output ./

# Edit configuration
vim environments/prod/config.yml

# Setup secrets
cp assets/vault-example.yml environments/prod/vault-prod.yml
vim environments/prod/vault-prod.yml
ansible-vault encrypt environments/prod/vault-prod.yml

# Validate configuration
vm-config validate --env prod

# Deploy
vm-config apply --env prod
```

## Security Notes

- Never commit unencrypted vault files
- Use strong, unique passwords for each environment
- Regularly rotate credentials
- Limit SSH key access to necessary personnel
- Use different database passwords per environment

For more information, see the main project documentation.

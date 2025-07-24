# VM Config Factory

Modular VM configuration framework with CLI for repeatable infrastructure patterns.

## Quick Start

```bash
# Install via uv
cd vm-config-factory
uv sync
uv pip install -e .

# Initialize new project (creates environments/dev/)
vm-config init grafana-postgres --env dev --output ./

# Configure your VMs in environments/dev/config.yml
# Setup secrets in vault file and encrypt it

# Apply configuration
vm-config apply --env dev
```

## Architecture

- **Framework**: Python-native template system with modular config layers
- **Templates**: Multi-VM service patterns (grafana-postgres, monitoring-stack)
- **Layers**: Reusable configuration components (base-os, docker, networking)
- **CLI**: Typer-based interface with rich output

## MVP Features

- Single template: `grafana-postgres` (2-VM stack)
- Config layers: base-os, docker, application, networking
- Ansible artifact generation
- Secret management via ansible-vault
- Idempotent operations

## Development

```bash
# Clone and setup
git clone <repo>
cd vm-config-factory
uv sync --dev

# Run tests
uv run pytest

# Install in development mode  
uv pip install -e .
```

## Template Structure

```
templates/grafana-postgres/
├── template.py         # Python template definition
├── config_schema.yml   # Environment config schema
└── assets/            # Static files (compose, configs)
```

## Layer Development

```
layers/
├── base_os.py         # User management, SSH hardening
├── docker.py          # Docker Engine + Compose
├── networking.py      # Nginx, SSL certificates
└── monitoring.py      # Logging, metrics collection
```

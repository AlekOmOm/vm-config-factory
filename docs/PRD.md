# VM Config Factory — Production Requirements Document

## 0. Meta
- **Doc Owner**: Alek
- **Last Updated**: 2025-07-24
- **Status**: Draft v0.2
- **Design Framework Applied**: 5-Step Design Process

---

## 1. Problem Statement

DevOps teams need repeatable, modular VM configuration patterns. Current approaches are either:
- Too specific (manual Ansible playbooks per project)
- Too complex (full infrastructure platforms)
- Not modular (can't compose/extend configurations)

**Core Need**: A config framework with CLI distribution that enables:
- Service template composition (multi-VM stacks like `grafana-postgres`)
- Modular config layers (base-os, runtime, application, networking)
- Easy extensibility for custom config specifications
- Cloud-agnostic patterns (AWS/GCP future support)

## 2. Goals / Success Criteria

| ID | Goal | Metric |
|----|------|--------|
| G1 | Template-driven deployment | `vm-config apply grafana-postgres` provisions 2-VM stack in <5min |
| G2 | Modular layer system | Custom config-layers integrate without framework changes |
| G3 | Idempotent operations | `vm-config apply` shows 0 changes on re-run |
| G4 | Framework extensibility | New service templates added via simple directory structure |

## 3. Architecture Philosophy

**Core Abstraction**: Configuration Framework + CLI Distribution
- **Framework**: Modular, composable config layer system
- **CLI**: Easy interface for framework consumption
- **Templates**: Pre-built service deployment patterns

**Key Insight**: Teams need both ease-of-use (CLI) and extensibility (framework)

## 4. Scope

### In-Scope (MVP)
- **Target Stack**: `grafana-postgres` (2-VM template)
- **Cloud Provider**: AWS EC2 (existing instances)
- **Config Layers**: base-os, docker, application, networking
- **Tools**: Ansible core, nginx/SSL (no load balancer permissions)
- **Interface**: CLI tool with config framework backend

### Out-of-Scope (Future)
- Multi-cloud abstraction (AWS/GCP)
- Complex orchestration (auto-scaling, healing)
- Infrastructure provisioning (VPC, security groups)
- Advanced CI/CD integration

### Assumptions
- Ubuntu 22.04 LTS target VMs
- SSH key authentication available
- Docker as required runtime on all VMs
- Internet egress for package installation

## 5. System Design

### 5.1 Architecture Overview

```
vm-config CLI
    ↓
Config Framework
    ↓
Service Templates → Config Layers → Ansible Execution
```

### 5.2 Directory Structure

```
vm-config-factory/
├── pyproject.toml                # uv dependency management
├── src/vmconfig/
│   ├── __main__.py              # CLI entrypoint
│   ├── cli/                     # Command handlers (Typer)
│   │   ├── init.py             # Template initialization
│   │   ├── apply.py            # Configuration application
│   │   └── validate.py         # Config validation
│   ├── framework/               # Core framework engine
│   │   ├── templates.py        # Template system (Python classes)
│   │   ├── layers.py           # Config layer composition
│   │   ├── validation.py       # Schema validation (Pydantic)
│   │   └── generators/         # Artifact generators
│   │       ├── ansible.py      # Ansible playbook generation
│   │       └── scripts.py      # Bash script generation
│   └── registry.py             # Template/layer registry
├── templates/                   # Service deployment patterns
│   ├── grafana-postgres/
│   │   ├── template.py         # Python template definition
│   │   ├── config_schema.yml   # Environment config schema
│   │   └── assets/             # Static files (compose, configs)
│   └── prometheus-stack/
├── layers/                      # Modular config layers (Python)
│   ├── base_os.py              # User management, SSH hardening
│   ├── docker.py               # Docker Engine + Compose
│   ├── networking.py           # Nginx, SSL certificates
│   └── monitoring.py           # Logging, metrics collection
├── environments/                # Generated environment configs
│   ├── dev/
│   │   ├── inventory.yml       # Ansible inventory (generated)
│   │   ├── playbook.yml        # Ansible playbook (generated)
│   │   ├── group_vars/         # Variables (generated)
│   │   └── scripts/            # Operational scripts (generated)
│   └── prod/
└── docs/
    ├── template_development.md  # How to create custom templates
    └── layer_development.md     # How to create custom layers
```

### 5.3 Framework Architecture

**Python-Native Template System**: Templates defined as Python classes for maximum flexibility

```python
# templates/grafana-postgres/template.py
from vmconfig.framework import ServiceTemplate, VMConfig
from vmconfig.layers import BaseOS, Docker, Grafana, PostgreSQL, Nginx

class GrafanaPostgresTemplate(ServiceTemplate):
    name = "grafana-postgres"
    description = "Grafana + PostgreSQL on separate VMs"
    
    def __init__(self):
        self.vms = {
            'grafana': VMConfig(
                layers=[BaseOS(), Docker(), Grafana(), Nginx()],
                services=['grafana', 'nginx'],
                dependencies=['postgres']  # Service dependency
            ),
            'postgres': VMConfig(
                layers=[BaseOS(), Docker(), PostgreSQL()],
                services=['postgresql']
            )
        }
    
    def validate_environment(self, env_config: dict) -> ValidationResult:
        """Custom validation logic for this template"""
        return self._validate_database_connectivity(env_config)
    
    def generate_artifacts(self, env_config: dict, output_dir: Path) -> List[Artifact]:
        """Generate Ansible playbooks, inventories, and scripts"""
        return [
            self._generate_ansible_playbook(env_config, output_dir),
            self._generate_inventory(env_config, output_dir),
            self._generate_operational_scripts(env_config, output_dir)
        ]
```

**Config Layer Composition**: Modular, reusable configuration components

```python
# layers/docker.py
from vmconfig.framework import ConfigLayer, AnsibleTask

class DockerLayer(ConfigLayer):
    name = "docker"
    dependencies = ["base-os"]
    
    def generate_ansible_tasks(self, vm_config: dict) -> List[AnsibleTask]:
        """Generate Ansible tasks for Docker installation"""
        return [
            AnsibleTask(
                name="Install Docker Engine",
                module="apt", 
                params={"name": ["docker-ce", "docker-compose-plugin"]}
            ),
            AnsibleTask(
                name="Configure Docker daemon",
                template="docker/daemon.json.j2",
                dest="/etc/docker/daemon.json",
                notify="restart docker"
            )
        ]
    
    def generate_scripts(self, vm_config: dict) -> Dict[str, str]:
        """Generate operational bash scripts"""
        return {
            "docker-health.sh": self._render_template("docker-health.sh.j2", vm_config),
            "docker-cleanup.sh": self._render_template("docker-cleanup.sh.j2", vm_config)
        }
```

### 5.4 Service Templates

**Template Structure**: Multi-VM service patterns

```yaml
# templates/grafana-postgres/template.yml
name: grafana-postgres
description: "Grafana + PostgreSQL on separate VMs"
vms:
  grafana:
    layers: [base-os, docker, application, networking]
    services: [grafana]
  postgres:  
    layers: [base-os, docker, application]
    services: [postgresql]
dependencies:
  - grafana → postgres (database connection)
```

## 6. CLI Interface Design

### 6.1 Core Commands

```bash
# Install vm-config (uv-based distribution)
uv tool install vm-config-factory

# Initialize new project from template
vm-config init grafana-postgres --env dev --output ./my-project

# Validate configuration before applying
vm-config validate --env dev

# Apply configuration to target VMs  
vm-config apply --env dev [--vm grafana] [--dry-run]

# List available templates and layers
vm-config list templates
vm-config list layers

# Generate custom template scaffolding
vm-config template create my-stack --vms web,db --layers base-os,docker

# Development commands
vm-config layer validate ./custom-layers/monitoring.py
vm-config template test grafana-postgres --env test
```

### 6.2 Configuration Management

**Environment Configuration**: Structured YAML with schema validation

```yaml
# environments/dev/config.yml
template: grafana-postgres
metadata:
  description: "Development environment"
  owner: "platform-team"

vms:
  grafana:
    host: 10.0.1.10
    ansible_user: ubuntu
    vars:
      grafana_admin_password: "{{vault.grafana.admin_password}}"
      grafana_database_url: "postgres://{{vault.postgres.user}}:{{vault.postgres.password}}@{{vms.postgres.host}}/grafana"
      
  postgres:
    host: 10.0.1.11
    ansible_user: ubuntu
    vars:
      postgres_password: "{{vault.postgres.password}}"
      postgres_grafana_user: "{{vault.postgres.user}}"
      postgres_databases: ["grafana"]

secrets:
  vault_file: vault-dev.yml  # Ansible vault encrypted
  
validation:
  connectivity_checks: true
  port_availability: [3000, 5432]
  ssl_cert_expiry: 30  # days warning
```

**Generated Artifacts**: Framework produces ready-to-execute Ansible

```yaml
# environments/dev/playbook.yml (auto-generated)
---
- name: Configure Grafana VM
  hosts: grafana
  become: yes
  roles:
    - base_os
    - docker
    - grafana
    - nginx_ssl
  
- name: Configure PostgreSQL VM  
  hosts: postgres
  become: yes
  roles:
    - base_os
    - docker
    - postgresql

- name: Verify service connectivity
  hosts: grafana
  tasks:
    - name: Test database connection
      uri:
        url: "http://localhost:3000/api/health"
        method: GET
      retries: 3
```

## 7. Technical Requirements

### 7.1 Functional Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR1 | Template initialization | `vm-config init` creates working environment config |
| FR2 | Multi-VM orchestration | Single command configures both Grafana + Postgres VMs |
| FR3 | Layer modularity | Custom layers integrate without framework modification |
| FR4 | Idempotent execution | Re-running commands produces no configuration drift |
| FR5 | Secret management | Vault-encrypted secrets never stored in plaintext |

### 7.2 Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR1 | Execution time: Full stack deployment <5 minutes |
| NFR2 | Extensibility: New layers added via directory drop-in |
| NFR3 | Portability: Framework works across dev/stage/prod environments |
| NFR4 | Observability: Clear logging and error reporting |

## 8. Implementation Strategy

### 8.1 Execution Context Architecture

**Hybrid approach with clear execution boundaries:**

```
[Dev Machine - Python/uv]          [Target VMs - Bash/Ansible]
├── vm-config CLI (Python)         ├── Generated Ansible playbooks
├── Template framework             ├── Service scripts (bash)
├── Config validation              └── Health checks (bash)  
└── Ansible orchestration ─────────→ SSH execution
```

**Key Insight**: Python handles complex logic locally; Ansible + Bash execute configuration on VMs.

### 8.2 Technology Stack

#### Local Development Environment
- **Framework & CLI**: Python 3.11+ with uv dependency management
- **Template Engine**: Jinja2 (native Python templating)
- **CLI Interface**: Typer + Rich (modern Python CLI experience)
- **Config Processing**: PyYAML for configuration handling
- **Validation**: Pydantic for schema validation
- **Testing**: pytest for framework testing

#### Target VM Environment  
- **Configuration Engine**: Ansible (idempotent execution via SSH)
- **Runtime Scripts**: Bash (health checks, service management)
- **Service Management**: systemd + Docker Compose
- **Dependencies**: Minimal - only what's needed for service operation

#### Generated Artifacts
- **Ansible Playbooks**: Generated from Python templates
- **Inventory Files**: Dynamic generation from environment configs
- **Service Scripts**: Bash scripts for operational tasks
- **Docker Compose**: Service definitions with templated variables

### 8.3 Development Phases

**Phase 1**: Python Framework Foundation
- Core template system (Python classes)
- Config layer composition engine
- CLI interface with rich UX
- `grafana-postgres` template implementation
- Ansible playbook generation

**Phase 2**: Extensibility + Team Integration
- Custom layer development API
- Template validation and testing
- Documentation and examples
- Team onboarding materials

**Phase 3**: Production Readiness
- Secret management (ansible-vault integration)
- Multi-environment configuration
- Error handling and debugging tools
- Performance optimization

## 9. Extensibility Model

### 9.1 Custom Config Layers (Python Development)

Teams create custom layers as Python classes following the framework API:

```python
# custom_layers/monitoring.py
from vmconfig.framework import ConfigLayer, AnsibleTask
from typing import List, Dict

class DatadogMonitoringLayer(ConfigLayer):
    """Custom layer for DataDog agent installation"""
    
    name = "datadog-monitoring"
    dependencies = ["base-os"]
    
    # Schema for layer-specific configuration
    config_schema = {
        "datadog_api_key": {"type": "string", "required": True},
        "datadog_tags": {"type": "array", "default": []},
        "log_collection": {"type": "boolean", "default": True}
    }
    
    def generate_ansible_tasks(self, vm_config: dict) -> List[AnsibleTask]:
        """Generate Ansible tasks for DataDog agent"""
        return [
            AnsibleTask(
                name="Add DataDog repository",
                apt_repository={
                    "repo": "deb https://apt.datadoghq.com/ stable 7",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Install DataDog agent",
                apt={"name": "datadog-agent", "state": "present"}
            ),
            AnsibleTask(
                name="Configure DataDog agent",
                template="datadog/datadog.yaml.j2",
                dest="/etc/datadog-agent/datadog.yaml",
                notify="restart datadog-agent"
            )
        ]
    
    def generate_scripts(self, vm_config: dict) -> Dict[str, str]:
        """Generate operational scripts"""
        return {
            "datadog-status.sh": self._render_script("datadog-status.sh.j2"),
            "datadog-logs.sh": self._render_script("datadog-logs.sh.j2") 
        }
    
    def validate_config(self, layer_config: dict) -> List[str]:
        """Custom validation logic"""
        errors = []
        if not layer_config.get("datadog_api_key"):
            errors.append("DataDog API key is required")
        return errors
```

**Layer Integration**: Drop-in directory structure for custom layers

```
custom_layers/
├── monitoring.py              # Layer definition
├── templates/
│   ├── datadog/
│   │   └── datadog.yaml.j2   # Jinja2 templates
│   └── scripts/
│       ├── datadog-status.sh.j2
│       └── datadog-logs.sh.j2
└── tests/
    └── test_monitoring.py     # pytest tests
```

### 9.2 Custom Service Templates

Create new multi-VM service patterns using the template API:

```python  
# custom_templates/monitoring_stack.py
from vmconfig.framework import ServiceTemplate, VMConfig
from vmconfig.layers import BaseOS, Docker
from custom_layers.monitoring import DatadogMonitoringLayer

class MonitoringStackTemplate(ServiceTemplate):
    """Prometheus + Grafana + AlertManager monitoring stack"""
    
    name = "monitoring-stack"
    description = "Complete monitoring stack with Prometheus, Grafana, and AlertManager"
    
    def __init__(self):
        self.vms = {
            'prometheus': VMConfig(
                layers=[BaseOS(), Docker(), PrometheusLayer()],
                services=['prometheus', 'alertmanager']
            ),
            'grafana': VMConfig(
                layers=[BaseOS(), Docker(), GrafanaLayer(), DatadogMonitoringLayer()],
                services=['grafana'],
                dependencies=['prometheus']
            )
        }
    
    def generate_docker_compose(self, vm_name: str, env_config: dict) -> str:
        """Generate VM-specific docker-compose.yml"""
        if vm_name == 'prometheus':
            return self._render_template('prometheus-compose.yml.j2', env_config)
        elif vm_name == 'grafana':
            return self._render_template('grafana-compose.yml.j2', env_config)
```

### 9.3 Framework Extension Points

**Template Registry**: Auto-discovery of custom templates

```python
# Register custom templates
from vmconfig.registry import TemplateRegistry

# Auto-discovery from installed packages
TemplateRegistry.discover_templates("custom_templates")

# Manual registration
TemplateRegistry.register(MonitoringStackTemplate())
```

**Layer Composition**: Mix built-in and custom layers

```python
# Use custom layers in any template
vm_config = VMConfig(
    layers=[
        BaseOS(),              # Built-in layer
        Docker(),              # Built-in layer  
        DatadogMonitoringLayer(), # Custom layer
        CustomSecurityLayer()   # Another custom layer
    ]
)
```

## 10. Future Considerations

### 10.1 Multi-Cloud Support
- Abstract cloud-specific networking (AWS Security Groups vs GCP Firewall)
- Provider-specific secret management integration
- Load balancer abstraction layer

### 10.2 Advanced Features
- Dependency graph visualization
- Configuration drift detection
- Rolling update strategies
- Integration with existing infrastructure tools

## 11. Success Metrics

- **Adoption**: 3+ teams using custom config layers within 3 months
- **Productivity**: 80% reduction in VM setup time vs manual approaches  
- **Reliability**: <5% configuration drift incidents post-deployment
- **Extensibility**: New service templates created by non-framework developers

## 12. Open Questions

1. **Layer Dependency Resolution**: How complex should dependency graphs become?
2. **State Management**: Should framework track VM state or remain stateless?
3. **Integration Points**: How to integrate with existing infrastructure tools (Terraform, etc.)?
4. **Performance**: What's the acceptable latency for multi-VM orchestration?

---

## 13. Design Process Application

This PRD applied the 5-Step Design Process:

1. **Requirements Challenge**: Separated "VM config" from "service deployment patterns"
2. **Ruthless Deletion**: Eliminated complex CI/CD, multi-cloud, custom testing initially  
3. **Optimization**: Focused on config layer modularity and template composability
4. **Acceleration**: Start with single template, build feedback loops
5. **Automation**: Framework extensibility over premature feature automation

**Key Insight**: Python framework enables rich team collaboration - templates and layers as code, not configuration files.
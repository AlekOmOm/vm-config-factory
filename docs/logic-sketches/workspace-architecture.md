# Workspace Architecture Design

## Current Structure (Single Template Per Workspace)
```
my-project/
├── templates/           ← Only one template type
├── assets/
└── environments/
    ├── dev/config.yml   ← template: grafana-postgres (implicit)
    └── prod/config.yml
```

**Limitations:**
- ❌ One template per workspace
- ❌ Template selection implicit from config.yml
- ❌ Need separate directories for different services
- ❌ No multi-service orchestration

## Proposed Structure (Multi-Template Workspace)
```
workspace/
├── initialized/
│   ├── grafana-postgres/
│   │   ├── templates/
│   │   ├── assets/
│   │   └── environments/
│   │       ├── dev/config.yml
│   │       └── prod/config.yml
│   ├── monitoring-stack/
│   │   ├── templates/
│   │   ├── assets/
│   │   └── environments/
│   └── api-gateway/
│       ├── templates/
│       ├── assets/
│       └── environments/
└── deployments/  # Optional: multi-template deployments
    ├── full-stack-dev.yml
    └── full-stack-prod.yml
```

## Enhanced CLI Commands

### Current:
```bash
vm-config init grafana-postgres --env dev     # Creates in current dir
vm-config apply --env dev                     # Template implicit from config.yml
```

### Proposed:
```bash
# Initialize templates (creates in initialized/)
vm-config init grafana-postgres --env dev
vm-config init monitoring-stack --env dev
vm-config init api-gateway --env dev

# Apply specific template + environment (explicit)
vm-config apply -t grafana-postgres -e dev
vm-config apply -t monitoring-stack -e prod
vm-config apply -t api-gateway -e dev

# List available initialized templates
vm-config list --initialized

# Deploy multiple templates together
vm-config deploy full-stack-dev.yml  # Optional: orchestrated deployments
```

## Benefits:
- ✅ **Multi-Template Workspace**: Manage multiple services in one place
- ✅ **Explicit Selection**: Choose template at runtime
- ✅ **Better Organization**: Clean separation of concerns
- ✅ **Scalable**: Add new templates without directory proliferation
- ✅ **Multi-Service Deployments**: Optional orchestration layer

## Migration Path:
1. **Phase 1**: Support both structures (backward compatibility)
2. **Phase 2**: Enhanced CLI with `-t` flag for template selection
3. **Phase 3**: Multi-template deployment orchestration 
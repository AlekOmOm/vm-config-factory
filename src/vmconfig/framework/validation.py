"""Configuration validation logic"""
from typing import Dict, Any, List
from vmconfig.framework.templates import ValidationResult, ServiceTemplate

def validate_environment_config(env_config: Dict[str, Any], template: ServiceTemplate) -> ValidationResult:
    """Validate environment configuration against template requirements"""
    
    errors = []
    warnings = []
    
    # Basic structure validation
    if not env_config.get("template"):
        errors.append("Missing 'template' field in configuration")
    
    if not env_config.get("vms"):
        errors.append("Missing 'vms' configuration")
    else:
        # Validate VM configurations
        vms_config = env_config["vms"]
        template_vms = template.vms if hasattr(template, 'vms') else {}
        
        # Check required VMs are present
        for vm_name in template_vms.keys():
            if vm_name not in vms_config:
                errors.append(f"Missing configuration for VM: {vm_name}")
            else:
                vm_config = vms_config[vm_name]
                
                # Validate required fields
                if not vm_config.get("host"):
                    errors.append(f"Missing 'host' for VM: {vm_name}")
                
                if not vm_config.get("ansible_user"):
                    warnings.append(f"No 'ansible_user' specified for VM: {vm_name}, will use default")
        
        # Check for unexpected VMs
        for vm_name in vms_config.keys():
            if vm_name not in template_vms:
                warnings.append(f"Unknown VM in configuration: {vm_name}")
    
    # Validate secrets configuration
    secrets_config = env_config.get("secrets")
    if secrets_config:
        if not secrets_config.get("vault_file"):
            warnings.append("Secrets configured but no vault_file specified")
    else:
        warnings.append("No secrets configuration found - consider using ansible-vault for sensitive data")
    
    # Template-specific validation
    try:
        template_validation = template.validate_environment(env_config)
        errors.extend(template_validation.errors)
        warnings.extend(template_validation.warnings)
    except Exception as e:
        errors.append(f"Template validation failed: {e}")
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

def validate_connectivity(env_config: Dict[str, Any]) -> ValidationResult:
    """Validate connectivity to target VMs"""
    errors = []
    warnings = []
    
    # This would implement actual SSH connectivity checks
    # For MVP, we'll skip the actual connection testing
    
    validation_config = env_config.get("validation", {})
    if validation_config.get("connectivity_checks", True):
        # Would implement SSH connectivity tests here
        pass
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

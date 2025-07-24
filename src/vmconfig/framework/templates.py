"""Template system core classes"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel

@dataclass
class VMConfig:
    """Configuration for a single VM in a template"""
    layers: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    vars: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Artifact:
    """Generated artifact (playbook, script, etc.)"""
    path: Path
    content: str
    artifact_type: str

class ServiceTemplate(ABC):
    """Base class for service templates"""
    
    name: str = ""
    description: str = ""
    
    def __init__(self):
        self.vms: Dict[str, VMConfig] = {}
    
    @abstractmethod
    def generate_initial_config(self, environment: str) -> Dict[str, Any]:
        """Generate initial environment configuration"""
        pass
    
    @abstractmethod
    def validate_environment(self, env_config: Dict[str, Any]) -> 'ValidationResult':
        """Validate environment configuration"""
        pass
    
    @abstractmethod
    def generate_artifacts(self, env_config: Dict[str, Any], output_dir: Path) -> List[Artifact]:
        """Generate deployment artifacts"""
        pass
    
    def generate_initial_assets(self, output_dir: Path) -> None:
        """Generate initial template assets (docker-compose, configs, etc.)"""
        # Default implementation - can be overridden
        pass

class TemplateRegistry:
    """Registry for service templates"""
    
    _templates: Dict[str, type] = {}
    
    @classmethod
    def register(cls, template_class: type) -> None:
        """Register a template class"""
        if hasattr(template_class, 'name') and template_class.name:
            cls._templates[template_class.name] = template_class
        else:
            cls._templates[template_class.__name__.lower().replace('template', '')] = template_class
    
    @classmethod
    def get_template(cls, name: str) -> Optional[type]:
        """Get template class by name"""
        return cls._templates.get(name)
    
    @classmethod
    def list_templates(cls) -> List[str]:
        """List all registered template names"""
        return list(cls._templates.keys())
    
    @classmethod
    def discover_templates(cls) -> None:
        """Discover and register templates from templates/ directory"""
        # This would scan the templates directory for Python modules
        # For MVP, we'll manually register in __init__
        pass

# Validation result classes
@dataclass
class ValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

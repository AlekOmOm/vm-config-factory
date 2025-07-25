"""Config layer system"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class AnsibleTask:
    """Ansible task definition"""
    name: str
    module: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    notify: Optional[str] = None
    when: Optional[str] = None
    become: Optional[bool] = None
    retries: Optional[int] = None
    delay: Optional[int] = None
    loop: Optional[Any] = None
    register: Optional[str] = None
    until: Optional[str] = None
    ignore_errors: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Ansible task dictionary"""
        task = {
            "name": self.name,
            self.module: self.params
        }
        
        if self.notify:
            task["notify"] = self.notify
        if self.when:
            task["when"] = self.when
        if self.become is not None:
            task["become"] = self.become
        if self.retries is not None:
            task["retries"] = self.retries
        if self.delay is not None:
            task["delay"] = self.delay
        if self.loop is not None:
            task["loop"] = self.loop
        if self.register is not None:
            task["register"] = self.register
        if self.until is not None:
            task["until"] = self.until
        if self.ignore_errors is not None:
            task["ignore_errors"] = self.ignore_errors
            
        return task

class ConfigLayer(ABC):
    """Base class for configuration layers"""
    
    name: str = ""
    description: str = ""
    dependencies: List[str] = []
    
    @abstractmethod
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate Ansible tasks for this layer"""
        pass
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate operational scripts"""
        return {}
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate Ansible handlers"""
        return []
    
    def validate_config(self, layer_config: Dict[str, Any]) -> List[str]:
        """Validate layer-specific configuration"""
        return []

class LayerRegistry:
    """Registry for config layers"""
    
    _layers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, layer_class: type) -> None:
        """Register a layer class"""
        if hasattr(layer_class, 'name') and layer_class.name:
            cls._layers[layer_class.name] = layer_class
        else:
            cls._layers[layer_class.__name__.lower().replace('layer', '')] = layer_class
    
    @classmethod
    def get_layer(cls, name: str) -> Optional[type]:
        """Get layer class by name"""
        return cls._layers.get(name)
    
    @classmethod
    def list_layers(cls) -> List[str]:
        """List all registered layer names"""
        return list(cls._layers.keys())
    
    @classmethod
    def discover_layers(cls) -> None:
        """Discover and register layers from layers/ directory"""
        # This would scan the layers directory for Python modules
        # For MVP, we'll manually register in __init__
        pass

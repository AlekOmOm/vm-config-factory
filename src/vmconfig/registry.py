"""Template and layer registry initialization"""
import importlib.util
import inspect
from vmconfig.framework.templates import TemplateRegistry, ServiceTemplate
from vmconfig.framework.layers import LayerRegistry

# Import built-in layers - using relative imports within package
try:
    import sys
    from pathlib import Path
    
    # Add layers directory to path
    layers_dir = Path(__file__).parent.parent.parent / "layers"
    if str(layers_dir) not in sys.path:
        sys.path.insert(0, str(layers_dir))
    
    from base_os import BaseOSLayer
    from docker import DockerLayer  
    from networking import NetworkingLayer
    from application import GrafanaLayer, PostgreSQLLayer
    from prometheus import PrometheusLayer

    
except ImportError as e:
    print(f"Warning: Could not import all components: {e}")
    # Define minimal fallbacks for testing
    class BaseOSLayer:
        name = "base-os"
    class DockerLayer:
        name = "docker"
    class NetworkingLayer:
        name = "networking"
    class GrafanaLayer:
        name = "grafana"
    class PostgreSQLLayer:
        name = "postgresql"
    class PrometheusLayer:
        name = "prometheus"


def discover_and_register_templates():
    """Autodiscover and register templates from templates/ directory"""
    try:
        templates_dir = Path(__file__).parent.parent.parent / "templates"
        
        if not templates_dir.exists():
            return
            
        for template_dir in templates_dir.iterdir():
            if not template_dir.is_dir() or template_dir.name.startswith('__'):
                continue
                
            template_file = template_dir / "template.py"
            if not template_file.exists():
                continue
                
            try:
                # Import the template module
                spec = importlib.util.spec_from_file_location(
                    f"template_{template_dir.name}", template_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find ServiceTemplate classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, ServiceTemplate) and 
                        obj != ServiceTemplate and 
                        hasattr(obj, 'name')):
                        TemplateRegistry.register(obj)
                        
            except Exception as e:
                print(f"Warning: Could not import template from {template_dir.name}: {e}")
                
    except Exception as e:
        print(f"Warning: Template discovery failed: {e}")

def initialize_registry():
    """Initialize template and layer registries with built-in components"""
    
    # Register built-in layers
    LayerRegistry.register(BaseOSLayer)
    LayerRegistry.register(DockerLayer)
    LayerRegistry.register(NetworkingLayer)
    LayerRegistry.register(GrafanaLayer)
    LayerRegistry.register(PostgreSQLLayer)
    LayerRegistry.register(PrometheusLayer)
    
    # Discover and register templates
    discover_and_register_templates()


# Initialize on import
try:
    initialize_registry()
except Exception as e:
    print(f"Warning: Registry initialization failed: {e}")

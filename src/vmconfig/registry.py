"""Template and layer registry initialization"""
from vmconfig.framework.templates import TemplateRegistry
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
    
    # Add templates directory to path
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    if str(templates_dir) not in sys.path:
        sys.path.insert(0, str(templates_dir))
    
    # Import templates
    sys.path.insert(0, str(templates_dir / "grafana-postgres"))
    from template import GrafanaPostgresTemplate
    
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
    class GrafanaPostgresTemplate:
        name = "grafana-postgres"

def initialize_registry():
    """Initialize template and layer registries with built-in components"""
    
    # Register built-in layers
    LayerRegistry.register(BaseOSLayer)
    LayerRegistry.register(DockerLayer)
    LayerRegistry.register(NetworkingLayer)
    LayerRegistry.register(GrafanaLayer)
    LayerRegistry.register(PostgreSQLLayer)
    
    # Register built-in templates
    TemplateRegistry.register(GrafanaPostgresTemplate)

# Initialize on import
try:
    initialize_registry()
except Exception as e:
    print(f"Warning: Registry initialization failed: {e}")

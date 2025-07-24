"""Layer validation command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
import importlib.util
import sys

from vmconfig.framework.layers import LayerRegistry, ConfigLayer

app = typer.Typer(help="Layer management commands")
console = Console()

@app.command("validate")
def validate_layer(
    layer_path: Path = typer.Argument(help="Path to layer Python file")
):
    """Validate a custom layer implementation"""
    
    console.print(f"[bold blue]Validating layer: {layer_path}[/bold blue]")
    
    try:
        if not layer_path.exists():
            console.print(f"[red]Error: Layer file not found: {layer_path}[/red]")
            raise typer.Exit(1)
        
        if not layer_path.suffix == '.py':
            console.print(f"[red]Error: Layer file must be a Python file (.py)[/red]")
            raise typer.Exit(1)
        
        # Load the module
        spec = importlib.util.spec_from_file_location("custom_layer", layer_path)
        if spec is None or spec.loader is None:
            console.print(f"[red]Error: Could not load Python module from {layer_path}[/red]")
            raise typer.Exit(1)
        
        module = importlib.util.module_from_spec(spec)
        sys.modules["custom_layer"] = module
        spec.loader.exec_module(module)
        
        # Find ConfigLayer subclasses in the module
        layer_classes = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, ConfigLayer) and 
                attr is not ConfigLayer):
                layer_classes.append(attr)
        
        if not layer_classes:
            console.print(f"[red]Error: No ConfigLayer subclasses found in {layer_path}[/red]")
            console.print("Layer must inherit from vmconfig.framework.layers.ConfigLayer")
            raise typer.Exit(1)
        
        # Validate each layer class
        errors = []
        warnings = []
        
        for layer_class in layer_classes:
            console.print(f"\n[cyan]Validating layer class: {layer_class.__name__}[/cyan]")
            
            try:
                # Instantiate the layer
                layer_instance = layer_class()
                
                # Check required attributes
                if not hasattr(layer_instance, 'name') or not layer_instance.name:
                    errors.append(f"{layer_class.__name__}: Missing or empty 'name' attribute")
                
                if not hasattr(layer_instance, 'description'):
                    warnings.append(f"{layer_class.__name__}: Missing 'description' attribute")
                
                if not hasattr(layer_instance, 'dependencies'):
                    warnings.append(f"{layer_class.__name__}: Missing 'dependencies' attribute")
                
                # Test required methods
                try:
                    tasks = layer_instance.generate_ansible_tasks({})
                    if not isinstance(tasks, list):
                        errors.append(f"{layer_class.__name__}: generate_ansible_tasks must return a list")
                    else:
                        console.print(f"  ✓ Generates {len(tasks)} Ansible tasks")
                except Exception as e:
                    errors.append(f"{layer_class.__name__}: Error in generate_ansible_tasks: {e}")
                
                try:
                    scripts = layer_instance.generate_scripts({})
                    if not isinstance(scripts, dict):
                        errors.append(f"{layer_class.__name__}: generate_scripts must return a dict")
                    else:
                        console.print(f"  ✓ Generates {len(scripts)} operational scripts")
                except Exception as e:
                    errors.append(f"{layer_class.__name__}: Error in generate_scripts: {e}")
                
                try:
                    handlers = layer_instance.generate_handlers()
                    if not isinstance(handlers, list):
                        errors.append(f"{layer_class.__name__}: generate_handlers must return a list")
                    else:
                        console.print(f"  ✓ Generates {len(handlers)} Ansible handlers")
                except Exception as e:
                    errors.append(f"{layer_class.__name__}: Error in generate_handlers: {e}")
                
                # Check dependencies exist
                if hasattr(layer_instance, 'dependencies'):
                    for dep in layer_instance.dependencies:
                        if not LayerRegistry.get_layer(dep):
                            warnings.append(f"{layer_class.__name__}: Dependency '{dep}' not found in registry")
                
                console.print(f"  ✓ Layer '{layer_instance.name}' structure is valid")
                
            except Exception as e:
                errors.append(f"{layer_class.__name__}: Failed to instantiate layer: {e}")
        
        # Display results
        if errors:
            console.print(f"\n[red]✗ Validation failed with {len(errors)} errors:[/red]")
            for error in errors:
                console.print(f"  - {error}")
        
        if warnings:
            console.print(f"\n[yellow]⚠ {len(warnings)} warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  - {warning}")
        
        if not errors:
            console.print(f"\n[green]✓ Layer validation passed for {len(layer_classes)} layer class(es)[/green]")
            
            # Show integration instructions
            console.print(f"\n[dim]Integration instructions:[/dim]")
            console.print(f"  1. Copy {layer_path} to layers/ directory")
            console.print(f"  2. Import and register in registry.py")
            console.print(f"  3. Add to template layer lists as needed")
        else:
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

@app.command("create")
def create_layer_template(
    name: str = typer.Argument(help="Layer name"),
    output: Path = typer.Option(Path.cwd(), "--output", "-o", help="Output directory")
):
    """Create a new layer template"""
    
    layer_file = output / f"{name.lower().replace('-', '_')}.py"
    
    if layer_file.exists():
        console.print(f"[red]Error: File already exists: {layer_file}[/red]")
        raise typer.Exit(1)
    
    template_content = f'''"""Custom {name} layer"""
from typing import Dict, List, Any
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class {name.title().replace('-', '')}Layer(ConfigLayer):
    """{name.title()} configuration layer"""
    
    name = "{name.lower()}"
    description = "{name.title()} configuration and management"
    dependencies = ["base-os"]  # Add your dependencies here
    
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate Ansible tasks for {name} configuration"""
        tasks = [
            AnsibleTask(
                name="Example task for {name}",
                module="debug",
                params={{"msg": "Configuring {name}"}}
            ),
            # Add your tasks here
        ]
        
        return tasks
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate Ansible handlers for {name}"""
        return [
            {{
                "name": "restart {name}",
                "service": {{
                    "name": "{name}",
                    "state": "restarted"
                }}
            }}
        ]
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate operational scripts for {name}"""
        return {{
            "{name}-status.sh": """#!/bin/bash
# {name.title()} status script
echo "=== {name.title()} Status ==="
# Add your status checks here
""",
            "{name}-restart.sh": """#!/bin/bash
# {name.title()} restart script  
echo "Restarting {name}..."
# Add your restart logic here
"""
        }}
    
    def validate_config(self, layer_config: Dict[str, Any]) -> List[str]:
        """Validate layer-specific configuration"""
        errors = []
        
        # Add your validation logic here
        # Example:
        # if not layer_config.get('required_param'):
        #     errors.append("Missing required_param")
        
        return errors
'''
    
    with layer_file.open('w') as f:
        f.write(template_content)
    
    console.print(f"[green]✓ Created layer template: {layer_file}[/green]")
    console.print(f"[dim]Next steps:[/dim]")
    console.print(f"  1. Edit {layer_file} to implement your layer logic")
    console.print(f"  2. Run: vm-config layer validate {layer_file}")
    console.print(f"  3. Integrate into your templates")

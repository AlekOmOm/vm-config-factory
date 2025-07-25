"""List templates and layers command"""
import typer
from rich.console import Console
from rich.table import Table

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.layers import LayerRegistry

app = typer.Typer(help="List available templates and layers")
console = Console()

@app.command("templates")
def list_templates():
    """List available templates"""
    templates = TemplateRegistry.list_templates()
    
    if not templates:
        console.print("[yellow]No templates found[/yellow]")
        return
    
    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("VMs")
    
    for template_name in templates:
        template_class = TemplateRegistry.get_template(template_name)
        template_instance = template_class()
        
        vm_count = len(template_instance.vms) if hasattr(template_instance, 'vms') else 0
        description = getattr(template_instance, 'description', 'No description')
        
        table.add_row(template_name, description, str(vm_count))
    
    console.print(table)

@app.command("layers")
def list_layers():
    """List available config layers"""
    layers = LayerRegistry.list_layers()
    
    if not layers:
        console.print("[yellow]No layers found[/yellow]")
        return
    
    table = Table(title="Available Config Layers")
    table.add_column("Name", style="cyan")
    table.add_column("Dependencies")
    table.add_column("Description")
    
    for layer_name in layers:
        layer_class = LayerRegistry.get_layer(layer_name)
        layer_instance = layer_class()
        
        dependencies = getattr(layer_instance, 'dependencies', [])
        description = getattr(layer_instance, 'description', 'No description')
        
        table.add_row(
            layer_name, 
            ", ".join(dependencies) if dependencies else "None",
            description
        )
    
    console.print(table)

@app.callback(invoke_without_command=True)
def main():
    """List all available templates and layers"""
    list_templates()
    console.print()
    list_layers()

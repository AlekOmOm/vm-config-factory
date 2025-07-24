"""Configuration validation command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.validation import validate_environment_config

app = typer.Typer(help="Validate configuration")
console = Console()

@app.command()
def main(
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    config_dir: Path = typer.Option(Path.cwd(), "--config-dir", "-c", help="Config directory")
):
    """Validate environment configuration"""
    
    console.print(f"[bold blue]Validating {env} environment configuration[/bold blue]")
    
    try:
        # Load environment config
        env_dir = config_dir / "environments" / env
        config_file = env_dir / "config.yml"
        
        if not config_file.exists():
            console.print(f"[red]Error: Config file not found: {config_file}[/red]")
            raise typer.Exit(1)
        
        # Load config
        import yaml
        with config_file.open() as f:
            env_config = yaml.safe_load(f)
        
        template_name = env_config.get("template")
        if not template_name:
            console.print("[red]Error: No template specified in config[/red]")
            raise typer.Exit(1)
        
        # Get template
        template_class = TemplateRegistry.get_template(template_name)
        if not template_class:
            console.print(f"[red]Error: Template '{template_name}' not found[/red]")
            raise typer.Exit(1)
        
        template_instance = template_class()
        
        # Validate configuration
        validation_result = validate_environment_config(env_config, template_instance)
        
        if validation_result.is_valid:
            console.print("[green]✓ Configuration is valid[/green]")
            
            # Show summary table
            table = Table(title="Configuration Summary")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details")
            
            table.add_row("Template", "✓", template_name)
            table.add_row("VMs", "✓", f"{len(env_config.get('vms', {}))} defined")
            table.add_row("Secrets", "✓" if env_config.get("secrets") else "⚠", 
                         "Vault configured" if env_config.get("secrets") else "No vault configured")
            
            console.print(table)
            
        else:
            console.print("[red]✗ Configuration validation failed[/red]")
            for i, error in enumerate(validation_result.errors, 1):
                console.print(f"  {i}. {error}")
            
            if validation_result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for i, warning in enumerate(validation_result.warnings, 1):
                    console.print(f"  {i}. {warning}")
            
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

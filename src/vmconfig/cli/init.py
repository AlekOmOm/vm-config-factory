"""Template initialization command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from typing import Optional

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.validation import validate_environment_config

app = typer.Typer(help="Initialize new project from template")
console = Console()

@app.command()
def main(
    template: str = typer.Argument(help="Template name (e.g., grafana-postgres)"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files")
):
    """Initialize new project from template"""
    
    # Resolve output directory
    if output is None:
        output = Path.cwd() / f"{template}-{env}"
    
    console.print(f"[bold blue]Initializing {template} template for {env} environment[/bold blue]")
    
    try:
        # Get template from registry
        template_class = TemplateRegistry.get_template(template)
        if not template_class:
            console.print(f"[red]Error: Template '{template}' not found[/red]")
            available = TemplateRegistry.list_templates()
            console.print(f"Available templates: {', '.join(available)}")
            raise typer.Exit(1)
        
        # Create output directory
        output.mkdir(parents=True, exist_ok=force)
        
        # Initialize template
        template_instance = template_class()
        
        # Generate initial environment config
        env_config = template_instance.generate_initial_config(env)
        
        # Create environment directory structure
        env_dir = output / "environments" / env
        env_dir.mkdir(parents=True, exist_ok=True)
        
        # Write config file
        config_file = env_dir / "config.yml"
        with config_file.open("w") as f:
            import yaml
            yaml.dump(env_config, f, default_flow_style=False)
        
        # Generate template assets
        template_instance.generate_initial_assets(output)
        
        console.print(f"[green]✓ Project initialized at {output}[/green]")
        console.print(f"[dim]Next steps:[/dim]")
        console.print(f"  1. Edit {config_file} with your VM details")
        console.print(f"  2. Run: vm-config validate --env {env}")
        console.print(f"  3. Run: vm-config apply --env {env}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

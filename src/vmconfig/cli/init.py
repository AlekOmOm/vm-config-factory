"""Template initialization command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from typing import Optional

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.validation import validate_environment_config

console = Console()

def init_command(
    template: str = typer.Argument(help="Template name (e.g., grafana-postgres)"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    skip_edit: bool = typer.Option(False, "--skip-edit", help="Skip the configuration edit prompt")
):
    if output is None:
        output = Path.cwd()
    
    # Create multi-template workspace structure
    template_dir = output / "initialized" / template
    console.print(f"[bold blue]Initializing {template} template for {env} environment[/bold blue]")
    console.print(f"[dim]Creating in: {template_dir}[/dim]")
    
    try:
        template_class = TemplateRegistry.get_template(template)
        if not template_class:
            console.print(f"[red]Error: Template '{template}' not found[/red]")
            available = TemplateRegistry.list_templates()
            console.print(f"Available templates: {', '.join(available)}")
            raise typer.Exit(1)
        
        # Check if template directory already exists
        template_exists = template_dir.exists()
        if template_exists and not force:
            console.print(f"[yellow]Template '{template}' already exists[/yellow]")
            console.print(f"[dim]Only creating {env} environment...[/dim]")
        else:
            template_dir.mkdir(parents=True, exist_ok=True)
        
        template_instance = template_class()
        env_config = template_instance.generate_initial_config(env)
        
        env_dir = template_dir / "environments" / env
        if env_dir.exists() and not force:
            console.print(f"[red]Environment '{env}' already exists for template '{template}'[/red]")
            console.print("Use --force to overwrite")
            raise typer.Exit(1)
        
        env_dir.mkdir(parents=True, exist_ok=True)
        config_file = env_dir / "config.yml"
        with config_file.open("w") as f:
            import yaml
            yaml.dump(env_config, f, default_flow_style=False)
        
        # Only generate assets if template is new or force is used
        if not template_exists or force:
            console.print(f"[dim]Generating template assets...[/dim]")
            template_instance.generate_initial_assets(template_dir)
        else:
            console.print(f"[dim]Reusing existing template assets...[/dim]")
        
        console.print(f"[green]✓ Environment '{env}' initialized for template '{template}'[/green]")
        console.print(f"[dim]Template location: {template_dir}[/dim]")
        console.print(f"[dim]Environment config: {config_file}[/dim]")
        
        # Prompt to edit configuration
        if not skip_edit:
            from vmconfig.cli.edit_config import prompt_edit_after_init
            prompt_edit_after_init(config_file, template, env)
        
        console.print(f"[dim]Next steps:[/dim]")
        console.print(f"  1. Run: vm-config validate -t {template} -e {env}")
        console.print(f"  2. Run: vm-config apply -t {template} -e {env}")
        console.print(f"  3. Or browse all: vm-config browse")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) 
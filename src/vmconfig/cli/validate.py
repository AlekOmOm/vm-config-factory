"""Configuration validation command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
import yaml
from typing import Optional

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.validation import validate_environment_config
from .lib.tui import TUI, InfoPanel

console = Console()

def validate_command(
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template name (e.g., grafana-postgres)"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    config_dir: Path = typer.Option(Path.cwd(), "--config-dir", "-c", help="Config directory")
):
    TUI.header("Validating configuration")

    try:
        # Use same discovery logic as apply
        if template:
            template_dir = config_dir / "initialized" / template
            if not template_dir.exists():
                TUI.error_message(f"Template '{template}' not initialized")
                raise typer.Exit(1)
            env_dir = template_dir / "environments" / env
        else:
            # Auto-discover single template
            initialized_dir = config_dir / "initialized"
            if initialized_dir.exists():
                templates = [d.name for d in initialized_dir.iterdir() if d.is_dir()]
                if len(templates) == 1:
                    template = templates[0]
                    env_dir = initialized_dir / template / "environments" / env
                elif len(templates) > 1:
                    TUI.error_message(f"Multiple templates found: {', '.join(templates)}")
                    console.print("Specify template with: vm-config validate -t <template> -e {env}")
                    TUI.spacer()
                    raise typer.Exit(1)
                else:
                    TUI.error_message("No templates found in initialized/")
                    raise typer.Exit(1)
            else:
                # Legacy structure
                env_dir = config_dir / "environments" / env

        config_file = env_dir / "config.yml"
        if not config_file.exists():
            TUI.error_message(f"Config file not found: {config_file}")
            raise typer.Exit(1)
        with config_file.open() as f:
            env_config = yaml.safe_load(f)
        
        # Use explicit template if provided, otherwise fall back to config
        if template:
            template_name = template
        else:
            template_name = env_config.get("template")
            if not template_name:
                TUI.error_message("No template specified in config")
                raise typer.Exit(1)
        
        template_class = TemplateRegistry.get_template(template_name)
        if not template_class:
            TUI.error_message(f"Template '{template_name}' not found")
            raise typer.Exit(1)
        template_instance = template_class()
        validation_result = validate_environment_config(env_config, template_instance)
        
        if validation_result.is_valid:
            TUI.success_message("Configuration is valid")
            
            table = Table(title="Configuration Summary", style="cyan")
            table.add_column("Component", style="cyan", width=15)
            table.add_column("Status", style="green", width=10)
            table.add_column("Details", width=25)
            
            table.add_row("Template", "✓", template_name)
            table.add_row("VMs", "✓", f"{len(env_config.get('vms', {}))} defined")
            table.add_row("Secrets", "✓" if env_config.get("secrets") else "⚠", 
                         "Vault configured" if env_config.get("secrets") else "No vault configured")
            
            console.print(table)
            TUI.spacer()
        else:
            TUI.error_message("Configuration validation failed")
            
            TUI.spacer()
            console.print("[bold red]Errors:[/bold red]")
            for i, error in enumerate(validation_result.errors, 1):
                console.print(f"  [red]{i}.[/red] {error}")
            
            if validation_result.warnings:
                TUI.spacer()
                console.print("[bold yellow]Warnings:[/bold yellow]")
                for i, warning in enumerate(validation_result.warnings, 1):
                    console.print(f"  [yellow]{i}.[/yellow] {warning}")
            
            TUI.spacer()
            raise typer.Exit(1)
            
    except Exception as e:
        TUI.error_message(str(e))
        raise typer.Exit(1) 
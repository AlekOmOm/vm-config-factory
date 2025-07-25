"""Configuration validation command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
import yaml
from typing import Optional

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.validation import validate_environment_config

console = Console()

def validate_command(
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template name (e.g., grafana-postgres)"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    config_dir: Path = typer.Option(Path.cwd(), "--config-dir", "-c", help="Config directory")
):
    console.print(f"[bold blue]Validating configuration[/bold blue]")

    try:
        # Use same discovery logic as apply
        if template:
            template_dir = config_dir / "initialized" / template
            if not template_dir.exists():
                console.print(f"[red]Error: Template '{template}' not initialized[/red]")
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
                    console.print(f"[red]Multiple templates found: {', '.join(templates)}[/red]")
                    console.print("Specify template with: vm-config validate -t <template> -e {env}")
                    raise typer.Exit(1)
                else:
                    console.print("[red]No templates found in initialized/[/red]")
                    raise typer.Exit(1)
            else:
                # Legacy structure
                env_dir = config_dir / "environments" / env

        config_file = env_dir / "config.yml"
        if not config_file.exists():
            console.print(f"[red]Error: Config file not found: {config_file}[/red]")
            raise typer.Exit(1)
        with config_file.open() as f:
            env_config = yaml.safe_load(f)
        
        # Use explicit template if provided, otherwise fall back to config
        if template:
            template_name = template
        else:
            template_name = env_config.get("template")
            if not template_name:
                console.print("[red]Error: No template specified in config[/red]")
                raise typer.Exit(1)
        
        template_class = TemplateRegistry.get_template(template_name)
        if not template_class:
            console.print(f"[red]Error: Template '{template_name}' not found[/red]")
            raise typer.Exit(1)
        template_instance = template_class()
        validation_result = validate_environment_config(env_config, template_instance)
        if validation_result.is_valid:
            console.print("[green]✓ Configuration is valid[/green]")
            table = Table(title="Configuration Summary")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details")
            table.add_row("Template", "✓", template_name)
            table.add_row("VMs", "✓", f"{len(env_config.get('vms', {}))} defined")
            table.add_row("Secrets", "✓" if env_config.get("secrets") else "⚠", "Vault configured" if env_config.get("secrets") else "No vault configured")
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
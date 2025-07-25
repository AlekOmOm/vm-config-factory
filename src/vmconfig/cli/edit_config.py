"""Interactive configuration editor command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from typing import Optional, Dict, Any
import yaml

from .lib.tui import TUI

console = Console()

def edit_config_command(
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template name"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Direct path to config.yml"),
    auto_prompt: bool = typer.Option(False, "--auto", help="Skip confirmation prompts")
):
    """Interactive configuration editor"""
    
    # Determine config file path
    if config_file:
        config_path = config_file
    elif template:
        config_path = Path.cwd() / "initialized" / template / "environments" / env / "config.yml"
    else:
        # Auto-discover
        initialized_dir = Path.cwd() / "initialized"
        if initialized_dir.exists():
            templates = [d.name for d in initialized_dir.iterdir() if d.is_dir()]
            if len(templates) == 1:
                template = templates[0]
                config_path = initialized_dir / template / "environments" / env / "config.yml"
            elif len(templates) > 1:
                console.print(f"[red]Multiple templates found: {', '.join(templates)}[/red]")
                console.print("Specify template with: vm-config edit -t <template> -e <env>")
                raise typer.Exit(1)
            else:
                console.print("[red]No templates found[/red]")
                raise typer.Exit(1)
        else:
            console.print("[red]No initialized templates found[/red]")
            raise typer.Exit(1)
    
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    # Load current config
    with config_path.open() as f:
        config = yaml.safe_load(f)
    
    # Interactive editing
    if not auto_prompt:
        TUI.header("Editing Configuration")
        console.print(f"[dim]Config file: {config_path}[/dim]")
        TUI.spacer()
    
    # Edit VM configurations
    if 'vms' in config:
        config['vms'] = edit_vms_section(config['vms'], auto_prompt)
    
    # Edit secrets section
    if 'secrets' in config:
        config['secrets'] = edit_secrets_section(config['secrets'], auto_prompt)
    
    # Edit vault file if it exists
    if 'secrets' in config and 'vault_file' in config['secrets']:
        vault_filename = config['secrets']['vault_file']
        vault_path = config_path.parent / vault_filename
        edit_vault_file(vault_path, auto_prompt)
    
    # Save changes
    if not auto_prompt:
        TUI.spacer()
        if not Confirm.ask("Save changes?", default=True):
            console.print("[yellow]Changes discarded[/yellow]")
            return
    
    with config_path.open('w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    if not auto_prompt:
        TUI.success_message(f"Configuration saved to {config_path}")
    else:
        console.print(f"[green]✓ Configuration saved to {config_path}[/green]")

def edit_vms_section(vms: Dict[str, Any], auto_prompt: bool = False) -> Dict[str, Any]:
    """Interactive editor for VMs section"""
    
    for vm_name, vm_config in vms.items():
        if not auto_prompt:
            TUI.section_header(f"Configuring {vm_name} VM", "bold cyan")
        
        # Edit host/connection details (handle both 'host' and 'ansible_host')
        if ('host' in vm_config or 'ansible_host' in vm_config) and not auto_prompt:
            current = vm_config.get('host', vm_config.get('ansible_host', ''))
            new_host = Prompt.ask(f"Host/IP address for {vm_name}", default=current)
            if new_host != current:
                if 'host' in vm_config:
                    vm_config['host'] = new_host
                else:
                    vm_config['ansible_host'] = new_host
        
        # Always prompt for SSH key (whether it exists or not)
        if not auto_prompt:
            current = vm_config.get('ssh_key_file', '')
            prompt_text = f"SSH private key file path for {vm_name}"
            if current:
                prompt_text += f" (current: {current})"
            else:
                prompt_text += " (required for SSH access)"
            
            new_key = Prompt.ask(prompt_text, default=current or "~/.ssh/id_rsa")
            if new_key and new_key != current:
                vm_config['ssh_key_file'] = new_key
        
        # Edit VM-specific variables
        if 'vars' in vm_config:
            vm_config['vars'] = edit_vm_vars(vm_name, vm_config['vars'], auto_prompt)
    
    return vms

def edit_vm_vars(vm_name: str, vars_config: Dict[str, Any], auto_prompt: bool = False) -> Dict[str, Any]:
    """Interactive editor for VM variables"""
    
    if auto_prompt:
        return vars_config
    
    # Key variables that should be edited
    editable_vars = {
        'grafana_domain': f"Domain for Grafana (current: {vars_config.get('grafana_domain', 'Not set')})",
        'grafana_database_host': f"Database host (current: {vars_config.get('grafana_database_host', 'Not set')})",
        'nginx_use_ssl': f"Enable nginx_use_ssl? [y/n]",
        'nginx_ssl_email': f"SSL notification email (current: {vars_config.get('nginx_ssl_email', 'Not set')})",
        'postgres_port': f"PostgreSQL port (current: {vars_config.get('postgres_port', 5432)})"
    }
    
    for var_name, description in editable_vars.items():
        if var_name in vars_config:
            current = vars_config[var_name]
            if isinstance(current, bool):
                new_value = Confirm.ask(f"Enable {var_name}?", default=current)
            else:
                new_value = Prompt.ask(description, default=str(current))
                # Convert back to appropriate type
                if var_name.endswith('_port'):
                    try:
                        new_value = int(new_value)
                    except ValueError:
                        pass
            
            if new_value != current:
                vars_config[var_name] = new_value
    
    return vars_config

def edit_secrets_section(secrets: Dict[str, Any], auto_prompt: bool = False) -> Dict[str, Any]:
    """Interactive editor for secrets section"""
    
    if auto_prompt:
        return secrets
    
    TUI.section_header("Secrets Configuration", "bold yellow")
    
    if 'vault_file' in secrets:
        current = secrets.get('vault_file', '')
        new_vault = Prompt.ask("Vault file name", default=current)
        if new_vault != current:
            secrets['vault_file'] = new_vault
    
    return secrets

def edit_vault_file(vault_path: Path, auto_prompt: bool = False) -> None:
    """Interactive editor for vault file containing passwords"""
    
    if auto_prompt:
        return
    
    if not vault_path.exists():
        console.print(f"[yellow]Vault file {vault_path.name} not found, skipping vault editing[/yellow]")
        return
    
    TUI.section_header("Vault Secrets", "bold red")
    console.print(f"[dim]Editing: {vault_path}[/dim]")
    console.print("[yellow]Warning: This file should be encrypted with ansible-vault in production![/yellow]")
    TUI.spacer()
    
    # Load vault file
    try:
        with vault_path.open() as f:
            vault_data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error reading vault file: {e}[/red]")
        return
    
    if not isinstance(vault_data, dict) or 'vault' not in vault_data:
        console.print("[red]Invalid vault file format[/red]")
        return
    
    vault_config = vault_data['vault']
    
    # Edit Grafana secrets
    if 'grafana' in vault_config:
        console.print("[cyan]Grafana Secrets:[/cyan]")
        grafana_secrets = vault_config['grafana']
        
        if 'admin_password' in grafana_secrets:
            current = grafana_secrets['admin_password']
            if current == "secure_admin_password_here":
                current = ""  # Don't show the placeholder as default
            new_password = Prompt.ask("Grafana admin password", default=current, password=True)
            if new_password:
                grafana_secrets['admin_password'] = new_password
    
    # Edit PostgreSQL secrets
    if 'postgres' in vault_config:
        console.print("[cyan]PostgreSQL Secrets:[/cyan]")
        postgres_secrets = vault_config['postgres']
        
        if 'admin_password' in postgres_secrets:
            current = postgres_secrets['admin_password']
            if current == "secure_postgres_password_here":
                current = ""
            new_password = Prompt.ask("PostgreSQL admin password", default=current, password=True)
            if new_password:
                postgres_secrets['admin_password'] = new_password
        
        if 'grafana_user' in postgres_secrets:
            current = postgres_secrets['grafana_user']
            new_user = Prompt.ask("PostgreSQL user for Grafana", default=current)
            if new_user:
                postgres_secrets['grafana_user'] = new_user
        
        if 'grafana_password' in postgres_secrets:
            current = postgres_secrets['grafana_password']
            if current == "secure_grafana_db_password_here":
                current = ""
            new_password = Prompt.ask("PostgreSQL password for Grafana user", default=current, password=True)
            if new_password:
                postgres_secrets['grafana_password'] = new_password
    
    # Save vault file
    if Confirm.ask("Update vault file?", default=True):
        with vault_path.open('w') as f:
            yaml.dump(vault_data, f, default_flow_style=False, sort_keys=False)
        console.print(f"[green]✓ Vault file updated: {vault_path}[/green]")
        console.print("[yellow]Remember to encrypt with: ansible-vault encrypt vault-{env}.yml[/yellow]")

def prompt_edit_after_init(config_path: Path, template: str, env: str) -> None:
    """Prompt user to edit config after init (helper for other commands)"""
    
    # TEMPORARY DEBUG: Skip interactive editing entirely for now
    TUI.spacer()
    console.print(f"[yellow]Debug mode: Skipping interactive editing for now[/yellow]")
    console.print(f"[dim]You can edit later with: vm-config edit -t {template} -e {env}[/dim]")
    TUI.spacer()
    return
    
    # Original code (commented out for debugging):
    """
    TUI.spacer()
    
    # Debug: Let's test the Confirm import first
    try:
        console.print(f"[blue]Debug: Testing Confirm class: {Confirm}[/blue]")
        console.print(f"[blue]Debug: Confirm.ask method: {Confirm.ask}[/blue]")
    except Exception as e:
        console.print(f"[red]Debug: Error with Confirm class: {e}[/red]")
        return
    
    if Confirm.ask(f"[bold]Edit {template} configuration for {env} environment?[/bold]", default=True):
        # Call the edit function directly
        try:
            import traceback
            edit_config_command(template=template, env=env, auto_prompt=False)
        except Exception as e:
            console.print(f"[red]Debug - Full error traceback:[/red]")
            traceback.print_exc()
            TUI.error_message(f"Error editing config: {e}")
    else:
        console.print(f"[dim]You can edit later with: vm-config edit -t {template} -e {env}[/dim]")
        TUI.spacer()
    """









"""Interactive configuration editor command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from typing import Optional, Dict, Any
import yaml

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
    console.print(Panel(f"[bold blue]Editing Configuration[/bold blue]\n{config_path}", border_style="blue"))
    
    # Edit VM configurations
    if 'vms' in config:
        config['vms'] = edit_vms_section(config['vms'])
    
    # Edit secrets section
    if 'secrets' in config:
        config['secrets'] = edit_secrets_section(config['secrets'])
    
    # Save changes
    if not auto_prompt:
        if not Confirm.ask("Save changes?", default=True):
            console.print("[yellow]Changes discarded[/yellow]")
            return
    
    with config_path.open('w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    console.print(f"[green]✓ Configuration saved to {config_path}[/green]")

def edit_vms_section(vms: Dict[str, Any]) -> Dict[str, Any]:
    """Interactive editor for VMs section"""
    
    for vm_name, vm_config in vms.items():
        console.print(f"\n[bold cyan]Configuring {vm_name} VM[/bold cyan]")
        
        # Edit host/connection details
        if 'ansible_host' in vm_config:
            current = vm_config.get('ansible_host', '')
            new_host = Prompt.ask(f"Ansible host for {vm_name}", default=current)
            if new_host != current:
                vm_config['ansible_host'] = new_host
        
        if 'ssh_key_file' in vm_config:
            current = vm_config.get('ssh_key_file', '')
            new_key = Prompt.ask(f"SSH key file for {vm_name}", default=current)
            if new_key != current:
                vm_config['ssh_key_file'] = new_key
        
        # Edit VM-specific variables
        if 'vars' in vm_config:
            vm_config['vars'] = edit_vm_vars(vm_name, vm_config['vars'])
    
    return vms

def edit_vm_vars(vm_name: str, vars_config: Dict[str, Any]) -> Dict[str, Any]:
    """Interactive editor for VM variables"""
    
    # Key variables that should be edited
    editable_vars = {
        'grafana_domain': f"Domain for Grafana (current: {vars_config.get('grafana_domain', 'Not set')})",
        'grafana_database_host': f"Database host (current: {vars_config.get('grafana_database_host', 'Not set')})",
        'nginx_use_ssl': f"Use SSL? (current: {vars_config.get('nginx_use_ssl', 'Not set')})",
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

def edit_secrets_section(secrets: Dict[str, Any]) -> Dict[str, Any]:
    """Interactive editor for secrets section"""
    
    console.print(f"\n[bold yellow]Secrets Configuration[/bold yellow]")
    
    if 'vault_file' in secrets:
        current = secrets.get('vault_file', '')
        new_vault = Prompt.ask("Vault file name", default=current)
        if new_vault != current:
            secrets['vault_file'] = new_vault
    
    return secrets

def prompt_edit_after_init(config_path: Path, template: str, env: str) -> None:
    """Prompt user to edit config after init (helper for other commands)"""
    
    if Confirm.ask(f"\n[bold]Edit {template} configuration for {env} environment?[/bold]", default=True):
        # Call the edit function directly
        try:
            edit_config_command(template=template, env=env, auto_prompt=True)
        except Exception as e:
            console.print(f"[red]Error editing config: {e}[/red]")
    else:
        console.print(f"[dim]You can edit later with: vm-config edit -t {template} -e {env}[/dim]")









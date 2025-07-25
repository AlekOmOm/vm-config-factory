"""Interactive configuration editor command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from typing import Optional, Dict, Any
import yaml
import re
import os
from subprocess import run, PIPE

from .lib.tui import TUI

console = Console()

def parse_ssh_config(ssh_alias: str) -> Optional[str]:
    """Parse SSH config to get actual hostname for an alias"""
    try:
        result = run(['ssh', '-G', ssh_alias], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.strip().startswith('hostname '):
                    return line.strip().split('hostname ')[1].strip()
    except Exception as e:
        TUI.debug_message(f"Could not resolve SSH config for {ssh_alias}: {e}")
    return None



def edit_config_command(
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template name (auto-detected if only one exists)"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Direct path to config.yml"),
    auto_prompt: bool = typer.Option(False, "--auto", help="Skip confirmation prompts"),
    vault_only: bool = typer.Option(False, "--vault-only", help="Edit only vault secrets (quick mode)")
):
    """🔧 Interactive configuration editor
    
    Examples:
        vm-config edit                    # Auto-detect template
        vm-config edit -t prometheus      # Edit prometheus template  
        vm-config edit --vault-only       # Quick vault editing
        vm-config edit -t grafana --auto  # Edit without prompts
    """
    
    # Determine config file path with better auto-discovery
    if config_file:
        config_path = config_file
        template = template or detect_template_from_path(config_file)
    elif template:
        config_path = Path.cwd() / "initialized" / template / "environments" / env / "config.yml"
    else:
        # Enhanced auto-discovery
        template, config_path = auto_discover_config(env)
    
    if not config_path.exists():
        TUI.error_message(f"Config file not found: {config_path}")
        suggest_initialization(template)
        raise typer.Exit(1)
    
    # Load current config
    with config_path.open() as f:
        config = yaml.safe_load(f)
    
    # Resolve SSH aliases with enhanced feedback
    config = resolve_ssh_aliases_with_feedback(config)
    
    # Interactive editing with better UX
    if not auto_prompt:
        TUI.header("VM Configuration Editor")
        console.print(f"[dim]Template: {template} | Environment: {env}[/dim]")
        console.print(f"[dim]Config: {config_path}[/dim]")
        TUI.spacer()
    
    # Vault-only mode for quick secret editing
    if vault_only:
        if 'secrets' in config and 'vault_file' in config['secrets']:
            vault_filename = config['secrets']['vault_file']
            vault_path = config_path.parent / vault_filename
            edit_vault_file(vault_path, auto_prompt, template)
        else:
            console.print("[yellow]No vault file configured[/yellow]")
        return
    
    # Edit VM configurations
    if 'vms' in config:
        # Show template-specific tips
        if template == "grafana-postgres" and not auto_prompt:
            TUI.info_message("💡 Tip: This template supports optional Prometheus data source integration for Grafana")
        
        config['vms'] = edit_vms_section(config['vms'], auto_prompt, template)
    
    # Edit secrets section
    if 'secrets' in config:
        config['secrets'] = edit_secrets_section(config['secrets'], auto_prompt)
    
    # Edit vault file if it exists
    if 'secrets' in config and 'vault_file' in config['secrets']:
        vault_filename = config['secrets']['vault_file']
        vault_path = config_path.parent / vault_filename
        edit_vault_file(vault_path, auto_prompt, template)
    
    # Save changes with better feedback
    if not auto_prompt:
        TUI.spacer()
        if not Confirm.ask("Save changes?", default=True):
            console.print("[yellow]Changes discarded[/yellow]")
            return
    
    with config_path.open('w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    if not auto_prompt:
        TUI.success_message(f"Configuration saved")
        show_next_steps(template, env)
    else:
        console.print(f"[green]✓ Configuration saved to {config_path}[/green]")

def detect_template_from_path(config_path: Path) -> Optional[str]:
    """Detect template name from config file path"""
    path_parts = config_path.parts
    if 'initialized' in path_parts:
        idx = path_parts.index('initialized')
        if idx + 1 < len(path_parts):
            return path_parts[idx + 1]
    return None

def auto_discover_config(env: str) -> tuple[Optional[str], Path]:
    """Enhanced auto-discovery of config files"""
    initialized_dir = Path.cwd() / "initialized"
    
    if not initialized_dir.exists():
        TUI.error_message("No initialized templates found")
        console.print("[yellow]Run: vm-config init <template> to create a new configuration[/yellow]")
        raise typer.Exit(1)
    
    templates = [d.name for d in initialized_dir.iterdir() if d.is_dir()]
    
    if len(templates) == 0:
        TUI.error_message("No templates found in initialized/")
        raise typer.Exit(1)
    elif len(templates) == 1:
        template = templates[0]
        config_path = initialized_dir / template / "environments" / env / "config.yml"
        console.print(f"[dim]Auto-detected template: {template}[/dim]")
        return template, config_path
    else:
        console.print(f"[yellow]Multiple templates found: {', '.join(templates)}[/yellow]")
        console.print("[yellow]Specify template with: vm-config edit -t <template>[/yellow]")
        
        table = Table(title="Available Templates")
        table.add_column("Template", style="cyan")
        table.add_column("Status", style="green")
        
        for template in templates:
            config_exists = (initialized_dir / template / "environments" / env / "config.yml").exists()
            status = "✓ Ready" if config_exists else "✗ Missing config"
            table.add_row(template, status)
        
        console.print(table)
        raise typer.Exit(1)

def suggest_initialization(template: str) -> None:
    """Suggest initialization commands when config is missing"""
    if template:
        console.print(f"[yellow]Initialize with: vm-config init {template} --env dev[/yellow]")
    else:
        console.print("[yellow]Initialize with: vm-config init <template> --env dev[/yellow]")

def resolve_ssh_aliases_with_feedback(config: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced SSH alias resolution with better user feedback"""
    if 'vms' not in config:
        return config
    
    console.print("[dim]🔍 Resolving SSH configurations...[/dim]")
    
    for vm_name, vm_config in config['vms'].items():
        if 'host' in vm_config:
            ssh_alias = vm_config['host']
            
            actual_hostname = parse_ssh_config(ssh_alias)
            if actual_hostname and actual_hostname != ssh_alias:
                console.print(f"[green]✓ SSH alias resolved: {ssh_alias} → {actual_hostname}[/green]")
                
                vm_config['ansible_host_alias'] = ssh_alias
                vm_config['actual_hostname'] = actual_hostname
                
                if 'vars' in vm_config:
                    vars_config = vm_config['vars']
                    for var_name, var_value in vars_config.items():
                        if isinstance(var_value, str) and ssh_alias in var_value:
                            if var_name.endswith('_domain') or 'domain' in var_name:
                                console.print(f"[green]✓ Updated {var_name}: {ssh_alias} → {actual_hostname}[/green]")
                                vars_config[var_name] = var_value.replace(ssh_alias, actual_hostname)
            else:
                if actual_hostname == ssh_alias:
                    console.print(f"[dim]• {vm_name}: {ssh_alias} (direct hostname)[/dim]")
                else:
                    console.print(f"[yellow]⚠ Could not resolve SSH alias: {ssh_alias}[/yellow]")
    
    return config

def show_next_steps(template: str, env: str) -> None:
    """Show helpful next steps after editing"""
    TUI.spacer()
    console.print("[bold cyan]Next Steps:[/bold cyan]")
    console.print(f"• Validate config: [green]vm-config validate -t {template} -e {env}[/green]")
    console.print(f"• Deploy changes: [green]vm-config apply -t {template} -e {env}[/green]")
    console.print(f"• Edit vault only: [green]vm-config edit -t {template} -e {env} --vault-only[/green]")
    
    # Template-specific tips
    if template == "grafana-postgres":
        TUI.spacer()
        console.print("[bold yellow]📊 Prometheus Integration:[/bold yellow]")
        console.print("• If you enabled Prometheus data source, ensure your Prometheus URL is accessible")
        console.print("• Grafana will automatically configure the data source on startup")
        console.print("• Access Grafana → Configuration → Data Sources to verify connection")

def edit_vms_section(vms: Dict[str, Any], auto_prompt: bool = False, template_name: str = None) -> Dict[str, Any]:
    """Interactive editor for VMs section"""
    
    for vm_name, vm_config in vms.items():
        if not auto_prompt:
            TUI.section_header(f"Configuring {vm_name} VM", "bold cyan")
        
        # Edit host/connection details (handle both 'host' and 'ansible_host')
        if ('host' in vm_config or 'ansible_host' in vm_config) and not auto_prompt:
            current = vm_config.get('host', vm_config.get('ansible_host', ''))
            console.print("[dim]Tip: You can use SSH config aliases (e.g., 'grafana', 'grafana-db') instead of full hostnames[/dim]")
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
            vm_config['vars'] = edit_vm_vars(vm_name, vm_config['vars'], auto_prompt, template_name)
    
    return vms

def edit_vm_vars(vm_name: str, vars_config: Dict[str, Any], auto_prompt: bool = False, template_name: str = None) -> Dict[str, Any]:
    """Template-aware interactive editor for VM variables"""
    
    if auto_prompt:
        return vars_config
    
    # Template-specific variable editing
    if template_name == "prometheus":
        editable_vars = {
            'prometheus_domain': f"Domain for Prometheus (current: {vars_config.get('prometheus_domain', 'Not set')})",
            'prometheus_port': f"Prometheus port (current: {vars_config.get('prometheus_port', 9090)})",
            'nginx_use_ssl': f"Enable SSL with nginx?",
            'nginx_ssl_email': f"SSL notification email (current: {vars_config.get('nginx_ssl_email', 'Not set')})",
        }
    elif template_name == "grafana-postgres":
        if vm_name == "grafana":
            # Grafana VM configuration
            editable_vars = {
                'grafana_domain': f"Domain for Grafana (current: {vars_config.get('grafana_domain', 'Not set')})",
                'grafana_database_host': f"Database host (current: {vars_config.get('grafana_database_host', 'Not set')})",
                'nginx_use_ssl': f"Enable SSL with nginx?",
                'nginx_ssl_email': f"SSL notification email (current: {vars_config.get('nginx_ssl_email', 'Not set')})",
                'prometheus_datasource_enabled': f"Enable Prometheus data source?",
                'prometheus_datasource_url': f"Prometheus URL (current: {vars_config.get('prometheus_datasource_url', 'Not set')})",
                'prometheus_datasource_name': f"Prometheus data source name (current: {vars_config.get('prometheus_datasource_name', 'Prometheus')})",
                'prometheus_datasource_access': f"Data source access method (current: {vars_config.get('prometheus_datasource_access', 'proxy')})"
            }
        elif vm_name == "postgres":
            # PostgreSQL VM configuration
            editable_vars = {
                'postgres_port': f"PostgreSQL port (current: {vars_config.get('postgres_port', 5432)})"
            }
        else:
            # Generic configuration for other VMs
            editable_vars = {}
    else:
        # Generic editing for unknown templates
        editable_vars = {}
        for key, value in vars_config.items():
            if isinstance(value, (str, int, bool)):
                editable_vars[key] = f"Current value: {value}"
    
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
        elif var_name.startswith('prometheus_datasource'):
            # Handle prometheus configuration for grafana-postgres template
            if var_name == 'prometheus_datasource_enabled':
                current = vars_config.get(var_name, False)
                console.print("\n[cyan]🔗 Prometheus Integration[/cyan]")
                console.print("[dim]Configure Grafana to automatically connect to your Prometheus instance[/dim]")
                new_value = Confirm.ask("Enable Prometheus data source in Grafana?", default=current)
                vars_config[var_name] = new_value
                
                if new_value:
                    # If enabling prometheus, prompt for required URL
                    current_url = vars_config.get('prometheus_datasource_url', 'http://your-prometheus-ip:9090')
                    if current_url == 'http://your-prometheus-ip:9090':
                        console.print("\n[yellow]⚠️  Please provide your Prometheus instance URL[/yellow]")
                        console.print("[dim]Example: http://203.0.113.10:9090 or http://prometheus.yourdomain.com[/dim]")
                    
                    new_url = Prompt.ask("Prometheus URL", default=current_url)
                    if new_url and new_url != current_url:
                        vars_config['prometheus_datasource_url'] = new_url
                    
                    # Optional: data source name
                    current_name = vars_config.get('prometheus_datasource_name', 'Prometheus')
                    new_name = Prompt.ask("Data source name in Grafana", default=current_name)
                    if new_name and new_name != current_name:
                        vars_config['prometheus_datasource_name'] = new_name
                    
                    # Optional: access method
                    current_access = vars_config.get('prometheus_datasource_access', 'proxy')
                    console.print("\n[dim]Access method:[/dim]")
                    console.print("[dim]• proxy: Grafana server connects to Prometheus (recommended)[/dim]")
                    console.print("[dim]• direct: Browser connects directly to Prometheus[/dim]")
                    new_access = Prompt.ask("Access method", choices=['proxy', 'direct'], default=current_access)
                    if new_access != current_access:
                        vars_config['prometheus_datasource_access'] = new_access
                else:
                    # If disabling prometheus, clean up related config
                    for key in ['prometheus_datasource_url', 'prometheus_datasource_name', 'prometheus_datasource_access']:
                        if key in vars_config:
                            del vars_config[key]
            elif vars_config.get('prometheus_datasource_enabled', False):
                # Only edit these if prometheus is enabled
                current = vars_config.get(var_name, '')
                if var_name == 'prometheus_datasource_access':
                    new_value = Prompt.ask(description, choices=['proxy', 'direct'], default=current or 'proxy')
                else:
                    new_value = Prompt.ask(description, default=current)
                
                if new_value and new_value != current:
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

def edit_vault_file(vault_path: Path, auto_prompt: bool = False, template_name: str = None) -> None:
    """Template-aware interactive editor for vault file containing passwords"""
    
    if auto_prompt:
        return
    
    if not vault_path.exists():
        console.print(f"[yellow]Vault file {vault_path.name} not found[/yellow]")
        if Confirm.ask("Create vault file?", default=True):
            create_default_vault_file(vault_path, template_name)
        else:
            return
    
    TUI.section_header("Vault Secrets", "bold red")
    TUI.info_message(f"Editing: {vault_path}")
    TUI.info_message("Warning: This file should be encrypted with ansible-vault in production!")
    TUI.spacer()
    
    # Load vault file
    try:
        with vault_path.open() as f:
            vault_data = yaml.safe_load(f)
    except Exception as e:
        TUI.error_message(f"Error reading vault file: {e}")
        return
    
    if not isinstance(vault_data, dict):
        TUI.error_message("Invalid vault file format")
        return
    
    # Template-aware vault editing
    if template_name == "prometheus":
        edit_prometheus_vault(vault_data)
    elif template_name == "grafana-postgres":
        edit_grafana_postgres_vault(vault_data)
    else:
        # Generic vault editing
        edit_generic_vault(vault_data)
    
    # Save vault file
    if Confirm.ask("Update vault file?", default=True):
        with vault_path.open('w') as f:
            yaml.dump(vault_data, f, default_flow_style=False, sort_keys=False)
        TUI.success_message(f"Vault file updated: {vault_path}")
        console.print(f"[yellow]Remember to encrypt with: ansible-vault encrypt {vault_path.name}[/yellow]")

def create_default_vault_file(vault_path: Path, template_name: str = None) -> None:
    """Create a default vault file based on template"""
    vault_data = {"vault": {}}
    
    if template_name == "prometheus":
        vault_data["vault"]["prometheus"] = {
            "admin_password": "secure_admin_password_here"
        }
    elif template_name == "grafana-postgres":
        vault_data["vault"]["grafana"] = {
            "admin_password": "secure_admin_password_here"
        }
        vault_data["vault"]["postgres"] = {
            "admin_password": "secure_postgres_password_here",
            "grafana_user": "grafana",
            "grafana_password": "secure_grafana_db_password_here"
        }
    else:
        vault_data["vault"]["secrets"] = {
            "admin_password": "secure_admin_password_here"
        }
    
    with vault_path.open('w') as f:
        yaml.dump(vault_data, f, default_flow_style=False, sort_keys=False)
    
    TUI.success_message(f"Created default vault file: {vault_path}")

def edit_prometheus_vault(vault_data: Dict[str, Any]) -> None:
    """Edit Prometheus-specific vault secrets"""
    if 'vault' not in vault_data:
        vault_data['vault'] = {}
    
    if 'prometheus' not in vault_data['vault']:
        vault_data['vault']['prometheus'] = {}
    
    prometheus_secrets = vault_data['vault']['prometheus']
    
    console.print("[cyan]Prometheus Secrets:[/cyan]")
    
    if 'admin_password' in prometheus_secrets:
        current = prometheus_secrets['admin_password']
        if current in ["secure_admin_password_here", "admin"]:
            current = ""  # Don't show placeholder as default
        new_password = Prompt.ask("Prometheus admin password", default=current, password=True)
        if new_password:
            prometheus_secrets['admin_password'] = new_password

def edit_grafana_postgres_vault(vault_data: Dict[str, Any]) -> None:
    """Edit Grafana-PostgreSQL-specific vault secrets"""
    if 'vault' not in vault_data:
        vault_data['vault'] = {}
    
    # Edit Grafana secrets
    if 'grafana' not in vault_data['vault']:
        vault_data['vault']['grafana'] = {}
    
    console.print("[cyan]Grafana Secrets:[/cyan]")
    grafana_secrets = vault_data['vault']['grafana']
    
    if 'admin_password' in grafana_secrets:
        current = grafana_secrets['admin_password']
        if current == "secure_admin_password_here":
            current = ""
        new_password = Prompt.ask("Grafana admin password", default=current, password=True)
        if new_password:
            grafana_secrets['admin_password'] = new_password
    
    # Edit PostgreSQL secrets
    if 'postgres' not in vault_data['vault']:
        vault_data['vault']['postgres'] = {}
    
    console.print("[cyan]PostgreSQL Secrets:[/cyan]")
    postgres_secrets = vault_data['vault']['postgres']
    
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

def edit_generic_vault(vault_data: Dict[str, Any]) -> None:
    """Edit generic vault secrets"""
    console.print("[cyan]Available secrets to edit:[/cyan]")
    
    def edit_dict_recursively(data: Dict[str, Any], path: str = ""):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            if isinstance(value, dict):
                console.print(f"[dim]{current_path}/[/dim]")
                edit_dict_recursively(value, current_path)
            elif isinstance(value, str) and ('password' in key.lower() or 'secret' in key.lower()):
                current_val = value if value not in ["secure_admin_password_here", "secure_postgres_password_here", "secure_grafana_db_password_here"] else ""
                new_value = Prompt.ask(f"Update {current_path}", default=current_val, password='password' in key.lower())
                if new_value:
                    data[key] = new_value
    
    if 'vault' in vault_data:
        edit_dict_recursively(vault_data['vault'])

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









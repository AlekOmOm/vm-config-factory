"""Configuration application command"""
import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from typing import Optional
import logging
import yaml
from subprocess import run

from vmconfig.framework.templates import TemplateRegistry
from vmconfig.framework.validation import validate_environment_config
from vmconfig.framework.generators.ansible import AnsibleGenerator
from .lib.tui import TUI

console = Console()

def resolve_ssh_aliases_in_config(config):
    """Resolve SSH aliases to actual hostnames - imported from edit_config"""
    def parse_ssh_config(ssh_alias: str) -> Optional[str]:
        """Parse SSH config to get actual hostname for an alias"""
        try:
            result = run(['ssh', '-G', ssh_alias], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('hostname '):
                        return line.strip().split('hostname ')[1].strip()
        except Exception:
            pass
        return None
    
    if 'vms' not in config:
        return config
    
    for vm_name, vm_config in config['vms'].items():
        if 'host' in vm_config:
            ssh_alias = vm_config['host']
            actual_hostname = parse_ssh_config(ssh_alias)
            if actual_hostname and actual_hostname != ssh_alias:
                console.print(f"[dim]Resolved SSH alias {ssh_alias} → {actual_hostname}[/dim]")
                vm_config['actual_hostname'] = actual_hostname
                
                # Update variables that reference other VMs
                if 'vars' in vm_config:
                    for var_name, var_value in vm_config['vars'].items():
                        if isinstance(var_value, str):
                            for other_vm_name, other_vm_config in config['vms'].items():
                                if other_vm_name != vm_name and 'host' in other_vm_config:
                                    other_alias = other_vm_config['host']
                                    other_actual = parse_ssh_config(other_alias)
                                    if other_actual and other_alias in var_value:
                                        vm_config['vars'][var_name] = var_value.replace(other_alias, other_actual)
    
    return config

def setup_simple_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')
    return logging.getLogger('vmconfig')

class SimpleProgressLogger:
    def __init__(self, logger, progress=None):
        self.logger = logger
        self.progress = progress
        self.current_task = None
    def start_task(self, description, total=None):
        if self.progress:
            self.current_task = self.progress.add_task(description, total=total)
        self.logger.info(f"Started: {description}")
    def update_task(self, description=None, advance=1):
        if self.progress and self.current_task is not None:
            if description:
                self.progress.update(self.current_task, description=description)
            self.progress.advance(self.current_task, advance)
    def complete_task(self, description=None):
        if description:
            self.logger.info(f"Completed: {description}")
        if self.progress and self.current_task is not None:
            self.progress.update(self.current_task, completed=True)
            self.current_task = None
    def error(self, message, exception=None):
        if exception:
            self.logger.error(f"{message}: {exception}")
        else:
            self.logger.error(message)

def apply_command(
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template name (e.g., grafana-postgres)"),
    env: str = typer.Option("dev", "--env", "-e", help="Environment name"),
    vm: Optional[str] = typer.Option(None, "--vm", help="Target specific VM only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done"),
    config_dir: Path = typer.Option(Path.cwd(), "--config-dir", "-c", help="Config directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    log_file: Optional[Path] = typer.Option(None, "--log-file", help="Log file path")
):
    logger = setup_simple_logging(verbose)
    
    # Auto-discover template if not specified
    if template:
        TUI.header(f"Applying {template} template for {env} environment")
        template_dir = config_dir / "initialized" / template
        if not template_dir.exists():
            TUI.error_message(f"Template '{template}' not initialized")
            console.print("Run 'vm-config init {template}' first")
            TUI.spacer()
            raise typer.Exit(1)
        env_dir = template_dir / "environments" / env
    else:
        # Legacy support: auto-discover single template
        TUI.header(f"Applying configuration for {env} environment")
        
        # Check for initialized/ structure first
        initialized_dir = config_dir / "initialized"
        if initialized_dir.exists():
            templates = [d.name for d in initialized_dir.iterdir() if d.is_dir()]
            if len(templates) == 1:
                template = templates[0]
                console.print(f"[dim]Auto-detected template: {template}[/dim]")
                env_dir = initialized_dir / template / "environments" / env
            elif len(templates) > 1:
                TUI.error_message(f"Multiple templates found: {', '.join(templates)}")
                console.print("Specify template with: vm-config apply -t <template> -e {env}")
                TUI.spacer()
                raise typer.Exit(1)
            else:
                TUI.error_message("No templates found in initialized/")
                raise typer.Exit(1)
        else:
            # Legacy single-template structure
            env_dir = config_dir / "environments" / env
    
    logger.info(f"Starting apply command for template: {template}, environment: {env}")
    try:
        config_file = env_dir / "config.yml"
        if not config_file.exists():
            TUI.error_message(f"Config file not found: {config_file}")
            console.print("Run 'vm-config init' first to initialize the project")
            logger.error(f"Config file not found: {config_file}")
            TUI.spacer()
            raise typer.Exit(1)
        with config_file.open() as f:
            env_config = yaml.safe_load(f)
        
        # Resolve SSH aliases to actual hostnames
        env_config = resolve_ssh_aliases_in_config(env_config)
        
        # Use explicit template if provided, otherwise fall back to config
        if template:
            template_name = template
        else:
            template_name = env_config.get("template")
            if not template_name:
                TUI.error_message("No template specified in config")
                logger.error("No template specified in configuration")
                raise typer.Exit(1)
        
        template_class = TemplateRegistry.get_template(template_name)
        if not template_class:
            TUI.error_message(f"Template '{template_name}' not found")
            available = TemplateRegistry.list_templates()
            console.print(f"[cyan]Available templates:[/cyan] {', '.join(available)}")
            logger.error(f"Template not found: {template_name}")
            TUI.spacer()
            raise typer.Exit(1)
        template_instance = template_class()
        validation_result = validate_environment_config(env_config, template_instance)
        if not validation_result.is_valid:
            TUI.error_message("Configuration validation failed")
            TUI.spacer()
            console.print("[bold red]Errors:[/bold red]")
            for error in validation_result.errors:
                console.print(f"  [red]•[/red] {error}")
                logger.error(f"Validation error: {error}")
            TUI.spacer()
            raise typer.Exit(1)
        if validation_result.warnings:
            console.print("[bold yellow]Configuration warnings:[/bold yellow]")
            for warning in validation_result.warnings:
                console.print(f"  [yellow]•[/yellow] {warning}")
                logger.warning(f"Validation warning: {warning}")
            TUI.spacer()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            progress_logger = SimpleProgressLogger(logger, progress)
            progress_logger.start_task("Generating Ansible artifacts...", total=3)
            try:
                ansible_gen = AnsibleGenerator(template_instance)

                vault_file = None
                if "secrets" in env_config and "vault_file" in env_config.get("secrets", {}):
                    vault_file = env_config["secrets"]["vault_file"]

                artifacts = ansible_gen.generate_artifacts(env_config, env_dir, vault_file=vault_file)
                progress_logger.update_task("Generated artifacts successfully", advance=1)
                
                use_vault = bool(vault_file)
                vault_file_encrypted = False
                vault_file_password = None
                if vault_file:
                    vault_file_encrypted = vault_file.endswith(".enc")

                if dry_run:
                    progress_logger.update_task("DRY RUN - Showing planned execution", advance=2)
                    console.print("[yellow]DRY RUN - Would execute:[/yellow]")
                    for artifact in artifacts:
                        console.print(f"  - {artifact.path}")
                    progress_logger.complete_task("Dry run completed")
                else:
                    progress_logger.update_task("Executing Ansible playbook...", advance=1)
                    if use_vault:
                        if vault_file_encrypted:
                            vault_file_password = env_config["secrets"]["vault_file_password"]
                        if not vault_file_password:
                            progress.stop()
                            TUI.error_message("\n[bold yellow]Ansible Vault password required.[/bold yellow]")
                            TUI.spacer()
                            TUI.info_message("[dim]Tip: You can set the password in the config file or use the --vault-file-password option.[/dim]")
                            TUI.info_message("[dim] - fx. vm-config apply --vault-file-password 'my_password'[/dim]")
                            TUI.spacer()
                            # continue without vault password
                    result = ansible_gen.execute_playbook(
                        playbook_path=env_dir / "playbook.yml",
                        inventory_path=env_dir / "inventory.yml",
                        target_vm=vm,
                        use_vault=use_vault,
                        cwd=env_dir,
                    )
                    if use_vault:
                        progress.start()
                    progress_logger.update_task("Ansible execution completed", advance=1)
                    if result.success:
                        progress_logger.complete_task("Configuration applied successfully")
                        TUI.success_message("Configuration applied successfully")
                        console.print(f"  [cyan]Changed:[/cyan] {result.changed_tasks}")
                        console.print(f"  [cyan]Failed:[/cyan] {result.failed_tasks}")
                        TUI.spacer()
                    else:
                        progress_logger.error("Configuration failed", None)
                        TUI.error_message("Configuration failed")
                        console.print(result.error_message)
                        if result.stderr:
                            logger.error(f"Ansible stderr: {result.stderr}")
                        TUI.spacer()
                        raise typer.Exit(1)
            except Exception as e:
                progress_logger.error("Apply failed", e)
                raise
    except Exception as e:
        if not isinstance(e, typer.Exit):
            TUI.error_message(str(e))
            logger.exception("Unexpected error during apply")
            raise typer.Exit(1)
        else:
            raise 
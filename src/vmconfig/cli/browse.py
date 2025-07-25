"""Interactive template and environment browser"""
import typer
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table
from typing import List, Dict, Tuple, Optional

console = Console()

def discover_initialized_templates() -> Dict[str, List[str]]:
    """Discover initialized templates and their environments"""
    initialized_dir = Path.cwd() / "initialized"
    templates = {}
    
    if not initialized_dir.exists():
        return templates
    
    for template_dir in initialized_dir.iterdir():
        if template_dir.is_dir():
            env_dir = template_dir / "environments"
            if env_dir.exists():
                environments = [env.name for env in env_dir.iterdir() if env.is_dir()]
                if environments:
                    templates[template_dir.name] = environments
    
    return templates

def show_overview():
    """Show overview of templates and environments"""
    console.print("\n" + "="*60)
    console.print("📊 VM Config Overview", style="bold blue")
    console.print("="*60)
    
    templates = discover_initialized_templates()
    
    if not templates:
        console.print("No initialized templates found.")
        console.print("Run 'vm-config init <template>' to get started")
    else:
        table = Table(title="Initialized Templates & Environments")
        table.add_column("Template", style="cyan")
        table.add_column("Environments", style="green")
        table.add_column("Count", style="yellow")
        
        for template_name, environments in templates.items():
            table.add_row(
                template_name,
                ", ".join(environments),
                str(len(environments))
            )
        
        console.print(table)
    
    console.print("\n[dim]Press Enter to continue...[/dim]")
    input()

def browse_templates():
    """Browse templates and environments"""
    console.print("\n" + "="*60)
    console.print("🔍 Browse Templates & Environments", style="bold green")
    console.print("="*60)
    
    templates = discover_initialized_templates()
    
    if not templates:
        console.print("No initialized templates found.")
        console.print("Run 'vm-config init <template>' to get started")
    else:
        for template_name, environments in templates.items():
            console.print(f"\n[bold cyan]{template_name}[/bold cyan]")
            for env in environments:
                console.print(f"  └── {env}")
    
    console.print("\n[dim]Press Enter to continue...[/dim]")
    input()

def show_quick_actions():
    """Show quick actions for templates and environments"""
    console.print(Panel("⚡ Quick Actions", style="bold yellow"))
    
    templates = discover_initialized_templates()
    
    if not templates:
        console.print("No initialized templates found.")
        console.print("Run 'vm-config init <template>' to get started")
        return False
    
    console.print("Available environments:")
    
    options = []
    index = 1
    for template_name, environments in templates.items():
        for env in environments:
            console.print(f"[{index}] {template_name} - {env}")
            console.print(f"    • vm-config edit -t {template_name} -e {env}")
            console.print(f"    • vm-config validate -t {template_name} -e {env}")
            console.print(f"    • vm-config apply -t {template_name} -e {env}")
            options.append((template_name, env))
            index += 1
    
    console.print("Actions:")
    console.print("   Copy all commands to clipboard")
    console.print("  [0] Back to main menu")
    
    while True:
        choice = Prompt.ask("Select environment (number) or action (0)", default="0")
        
        if choice == "0":
            return True
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                template_name, env = options[choice_idx]
                return handle_environment_actions(template_name, env)
            else:
                console.print("[red]Invalid selection[/red]")
        except ValueError:
            console.print("[red]Please enter a number[/red]")

def handle_environment_actions(template: str, env: str) -> bool:
    """Handle actions for a specific environment"""
    while True:
        console.print(f"\n🎯 {template} - {env}")
        console.print("Available commands:")
        console.print("   Run all (edit → validate → apply)")
        console.print("  [1] Edit configuration")
        console.print("  [2] Validate configuration") 
        console.print("  [3] Apply configuration")
        console.print("  [0] Back to environment list")
        
        action = Prompt.ask("Choose action [a/1/2/3/0/q]", default="a")
        
        if action in ["q", "quit"]:
            return False
        elif action == "0":
            return True
        elif action == "a":
            console.print("Running full workflow...")
            success = True
            success &= run_command(f"vm-config edit -t {template} -e {env}")
            if success:
                success &= run_command(f"vm-config validate -t {template} -e {env}")
            if success:
                success &= run_command(f"vm-config apply -t {template} -e {env}")
        elif action == "1":
            console.print(f"Executing: vm-config edit -t {template} -e {env}")
            run_command(f"vm-config edit -t {template} -e {env}")
        elif action == "2":
            console.print(f"Executing: vm-config validate -t {template} -e {env}")
            run_command(f"vm-config validate -t {template} -e {env}")
        elif action == "3":
            console.print(f"Executing: vm-config apply -t {template} -e {env}")
            run_command(f"vm-config apply -t {template} -e {env}")
        else:
            console.print("[red]Invalid choice[/red]")

def run_command(cmd: str) -> bool:
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd.split(), check=True, capture_output=True, text=True)
        console.print("✓ Command completed successfully")
        if result.stdout:
            console.print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"✗ Command failed: {e}")
        if e.stderr:
            console.print(f"[red]{e.stderr}[/red]")
        return False
    except Exception as e:
        console.print(f"✗ Command failed: {e}")
        return False

def browse_command():
    """Main browse command interface"""
    console.print("💡 Tip: Press 'q' anytime to quit")
    console.print("="*60)
    
    while True:
        console.print(Panel("VM Config - Interactive Browser", style="bold blue"))
        
        console.print("Available Options:")
        console.print("  [1] 📊 Show Overview")
        console.print("  [2] 🔍 Browse Templates & Environments") 
        console.print("  [3] ⚡ Quick Actions")
        console.print("   🚪 Quit")
        
        choice = Prompt.ask("Choose option [1/2/3/q]", default="2")
        
        if choice in ["q", "quit"]:
            break
        elif choice == "1":
            show_overview()
        elif choice == "2":
            browse_templates()
        elif choice == "3":
            if not show_quick_actions():
                break
        else:
            console.print("[red]Invalid choice[/red]") 
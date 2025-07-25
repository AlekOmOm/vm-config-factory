"""Interactive template and environment browser"""
import typer
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from typing import List, Dict, Tuple, Optional

from .lib.tui import TUI, Menu, InfoPanel, ActionMenu

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
    TUI.header("VM Config Overview")
    
    templates = discover_initialized_templates()
    
    if not templates:
        InfoPanel.show_no_templates()
    else:
        InfoPanel.show_templates_table(templates)
    
    TUI.wait_for_enter()

def browse_templates():
    """Browse templates and environments"""
    TUI.header("Browse Templates & Environments")
    
    templates = discover_initialized_templates()
    
    if not templates:
        InfoPanel.show_no_templates()
    else:
        InfoPanel.show_templates_tree(templates)
    
    TUI.wait_for_enter()

def show_quick_actions():
    """Show quick actions for templates and environments"""
    templates = discover_initialized_templates()
    
    if not templates:
        TUI.header("Quick Actions")
        InfoPanel.show_no_templates()
        TUI.wait_for_enter()
        return True
    
    options = ActionMenu.show_environment_list(templates)
    
    while True:
        choice = input("Select environment (number) or action [0]: ").strip()
        
        if choice == "0" or choice.lower() == "q":
            return True
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                template_name, env = options[choice_idx]
                if not handle_environment_actions(template_name, env):
                    return False
                break
            else:
                TUI.error_message("Invalid selection")
        except ValueError:
            TUI.error_message("Please enter a number")

def handle_environment_actions(template: str, env: str) -> bool:
    """Handle actions for a specific environment"""
    while True:
        action = ActionMenu.show_environment_actions(template, env)
        
        if action.lower() == "q":
            return False
        elif action == "0":
            return True
        elif action == "a":
            console.print("🔄 Running full workflow...", style="bold yellow")
            TUI.spacer()
            
            success = True
            success &= run_command(f"vm-config edit -t {template} -e {env}")
            if success:
                success &= run_command(f"vm-config validate -t {template} -e {env}")
            if success:
                success &= run_command(f"vm-config apply -t {template} -e {env}")
                
            TUI.wait_for_enter("Press Enter to continue...")
            
        elif action == "1":
            console.print(f"🔧 Executing: vm-config edit -t {template} -e {env}", style="bold cyan")
            TUI.spacer()
            run_command(f"vm-config edit -t {template} -e {env}")
            TUI.wait_for_enter()
            
        elif action == "2":
            console.print(f"✅ Executing: vm-config validate -t {template} -e {env}", style="bold blue")
            TUI.spacer()
            run_command(f"vm-config validate -t {template} -e {env}")
            TUI.wait_for_enter()
            
        elif action == "3":
            console.print(f"🚀 Executing: vm-config apply -t {template} -e {env}", style="bold green")
            TUI.spacer()
            run_command(f"vm-config apply -t {template} -e {env}")
            TUI.wait_for_enter()
            
        else:
            TUI.error_message("Invalid choice")

def run_command(cmd: str) -> bool:
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd.split(), check=True, capture_output=True, text=True)
        TUI.success_message("Command completed successfully")
        if result.stdout:
            console.print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        TUI.error_message(f"Command failed: {e}")
        if e.stderr:
            console.print(f"[red]{e.stderr}[/red]")
        return False
    except Exception as e:
        TUI.error_message(f"Command failed: {e}")
        return False

def browse_command():
    """Main browse command interface"""
    TUI.info_message("Press 'q' anytime to quit")
    
    while True:
        menu = Menu(
            "VM Config - Interactive Browser",
            [
                ("1", "📊 Show Overview"),
                ("2", "🔍 Browse Templates & Environments"),
                ("3", "⚡ Quick Actions"),
                ("q", "Quit")
            ],
            default_choice="2"
        )
        
        choice = menu.show()
        
        if choice.lower() == "q":
            break
        elif choice == "1":
            show_overview()
        elif choice == "2":
            browse_templates()
        elif choice == "3":
            if not show_quick_actions():
                break 
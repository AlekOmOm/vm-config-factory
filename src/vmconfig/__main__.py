"""VM Config Factory - CLI entrypoint"""
import typer
from rich.console import Console
from vmconfig.cli import init, apply, validate, list_cmd, layer, edit_config, browse
# Initialize registries on import
from vmconfig import registry

console = Console()
app = typer.Typer(
    name="vm-config",
    help="Modular VM configuration framework",
    rich_markup_mode="rich"
)

app.command("init", help="Initialize new project from template")(init.init_command)
app.command("apply", help="Apply configuration to target VMs")(apply.apply_command)
app.command("validate", help="Validate configuration")(validate.validate_command)
app.command("edit", help="Interactive configuration editor")(edit_config.edit_config_command)
app.command("browse", help="Interactive template and environment browser")(browse.browse_command)
app.add_typer(list_cmd.app, name="list")
app.add_typer(layer.app, name="layer")

def main():
    """Main CLI entrypoint"""
    app()

if __name__ == "__main__":
    main()

"""VM Config Factory - CLI entrypoint"""
import typer
from rich.console import Console
from vmconfig.cli import init, apply, validate, list_cmd, layer
# Initialize registries on import
from vmconfig import registry

console = Console()
app = typer.Typer(
    name="vm-config",
    help="Modular VM configuration framework",
    rich_markup_mode="rich"
)

app.add_typer(init.app, name="init")
app.add_typer(apply.app, name="apply") 
app.add_typer(validate.app, name="validate")
app.add_typer(list_cmd.app, name="list")
app.add_typer(layer.app, name="layer")

def main():
    """Main CLI entrypoint"""
    app()

if __name__ == "__main__":
    main()

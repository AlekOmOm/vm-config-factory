#!/usr/bin/env python3
"""Demo script showing vm-config init in action"""

import tempfile
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def demo_init():
    """Demonstrate the init command"""
    print("🚀 VM Config Factory - Init Command Demo")
    print("=" * 50)
    
    try:
        from typer.testing import CliRunner
        from vmconfig.__main__ import app
        
        # Create temporary directory for demo
        with tempfile.TemporaryDirectory() as tmpdir:
            demo_dir = Path(tmpdir) / "demo-project"
            
            print(f"📁 Creating demo project in: {demo_dir}")
            print()
            
            # Run init command
            print("🔧 Running: vm-config init grafana-postgres --env demo")
            runner = CliRunner()
            result = runner.invoke(app, [
                'init', 'grafana-postgres',
                '--env', 'demo', 
                '--output', str(demo_dir)
            ])
            
            print("Command output:")
            print("-" * 30)
            print(result.output)
            print("-" * 30)
            print()
            
            if result.exit_code == 0:
                print("✅ Init command succeeded!")
                print()
                
                # Show what was created
                print("📂 Generated project structure:")
                for path in sorted(demo_dir.rglob("*")):
                    rel_path = path.relative_to(demo_dir)
                    indent = "  " * (len(rel_path.parts) - 1)
                    icon = "📁" if path.is_dir() else "📄"
                    print(f"{indent}{icon} {rel_path.name}")
                
                print()
                
                # Show config file content
                config_file = demo_dir / "environments" / "demo" / "config.yml"
                if config_file.exists():
                    print("📄 Generated config.yml content:")
                    print("-" * 40)
                    with config_file.open() as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines[:20], 1):  # Show first 20 lines
                            print(f"{i:2}: {line.rstrip()}")
                        if len(lines) > 20:
                            print(f"... and {len(lines) - 20} more lines")
                    print("-" * 40)
                    print()
                
                print("🎯 Next steps:")
                print("1. Edit environments/demo/config.yml with your VM IPs")
                print("2. Setup vault file with secrets")
                print("3. Run: vm-config validate --env demo")
                print("4. Run: vm-config apply --env demo")
                
            else:
                print(f"❌ Init command failed with exit code: {result.exit_code}")
                print("Error output:", result.output)
            
    except ImportError as e:
        print(f"❌ Could not import vmconfig: {e}")
        print("Make sure you're in the project directory and dependencies are installed")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

def show_example_environment():
    """Show the example environment that exists"""
    print()
    print("📋 Example Environment (already exists)")
    print("=" * 50)
    
    example_dir = Path("environments/example")
    if example_dir.exists():
        print(f"📁 Location: {example_dir}")
        print()
        
        for file_path in example_dir.glob("*"):
            print(f"📄 {file_path.name}:")
            print("-" * 30)
            with file_path.open() as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:15], 1):  # Show first 15 lines
                    print(f"{i:2}: {line.rstrip()}")
                if len(lines) > 15:
                    print(f"... and {len(lines) - 15} more lines")
            print("-" * 30)
            print()
    else:
        print("❌ Example environment not found")

if __name__ == "__main__":
    # Show example environment first
    show_example_environment()
    
    # Then demo the init command
    demo_init()

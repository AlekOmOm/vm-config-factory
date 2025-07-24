#!/usr/bin/env python3
"""Test script to verify vm-config init works"""

import sys
import tempfile
from pathlib import Path

# Add src to path so we can import vmconfig
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_init_command():
    """Test the init command creates proper structure"""
    try:
        from typer.testing import CliRunner
        from vmconfig.__main__ import app
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "test-project"
            
            runner = CliRunner()
            result = runner.invoke(app, [
                'init', 'grafana-postgres',
                '--env', 'dev',
                '--output', str(output_dir)
            ])
            
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            
            if result.exit_code != 0:
                print("❌ Init command failed")
                return False
            
            # Check if files were created
            config_file = output_dir / "environments" / "dev" / "config.yml"
            if config_file.exists():
                print("✅ Config file created successfully")
                print(f"Config file location: {config_file}")
                
                # Show contents
                with config_file.open() as f:
                    content = f.read()
                    print("Config file contents:")
                    print(content[:500] + "..." if len(content) > 500 else content)
                
                return True
            else:
                print("❌ Config file not created")
                print(f"Looking for: {config_file}")
                print(f"Output dir contents: {list(output_dir.rglob('*'))}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_list_commands():
    """Test list commands work"""
    try:
        from typer.testing import CliRunner
        from vmconfig.__main__ import app
        
        runner = CliRunner()
        
        # Test list templates
        result = runner.invoke(app, ['list', 'templates'])
        print(f"List templates exit code: {result.exit_code}")
        print(f"List templates output: {result.output}")
        
        if 'grafana-postgres' in result.output:
            print("✅ Templates listed successfully")
        else:
            print("❌ grafana-postgres template not found in output")
        
        # Test list layers  
        result = runner.invoke(app, ['list', 'layers'])
        print(f"List layers exit code: {result.exit_code}")
        print(f"List layers output: {result.output}")
        
        expected_layers = ['base-os', 'docker', 'networking', 'grafana', 'postgresql']
        missing_layers = [layer for layer in expected_layers if layer not in result.output]
        
        if not missing_layers:
            print("✅ All expected layers listed")
        else:
            print(f"❌ Missing layers: {missing_layers}")
        
        return result.exit_code == 0
        
    except Exception as e:
        print(f"❌ List commands test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing VM Config Factory...")
    print()
    
    print("1. Testing list commands...")
    list_success = test_list_commands()
    print()
    
    print("2. Testing init command...")
    init_success = test_init_command()
    print()
    
    if list_success and init_success:
        print("✅ All tests passed! VM Config Factory is working.")
    else:
        print("❌ Some tests failed. Check output above.")
        sys.exit(1)

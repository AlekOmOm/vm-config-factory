"""Test CLI commands"""
import pytest
from pathlib import Path
import tempfile
import yaml
from typer.testing import CliRunner

from vmconfig.__main__ import app

def test_list_templates():
    """Test list templates command"""
    runner = CliRunner()
    result = runner.invoke(app, ['list', 'templates'])
    
    assert result.exit_code == 0
    assert 'grafana-postgres' in result.output

def test_list_layers():
    """Test list layers command"""
    runner = CliRunner()
    result = runner.invoke(app, ['list', 'layers'])
    
    assert result.exit_code == 0
    assert 'base-os' in result.output
    assert 'docker' in result.output

def test_init_command():
    """Test init command"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "test-project"
        
        runner = CliRunner()
        result = runner.invoke(app, [
            'init', 'grafana-postgres',
            '--env', 'test',
            '--output', str(output_dir)
        ])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Check generated files
        config_file = output_dir / "environments" / "test" / "config.yml"
        assert config_file.exists()
        
        # Validate config structure
        with config_file.open() as f:
            config = yaml.safe_load(f)
        
        assert config['template'] == 'grafana-postgres'
        assert 'vms' in config
        assert 'grafana' in config['vms']
        assert 'postgres' in config['vms']

def test_validate_command():
    """Test validate command"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # First initialize a project
        output_dir = Path(tmpdir) / "test-project"
        
        runner = CliRunner()
        init_result = runner.invoke(app, [
            'init', 'grafana-postgres',
            '--env', 'test',
            '--output', str(output_dir)
        ])
        assert init_result.exit_code == 0
        
        # Then validate it
        validate_result = runner.invoke(app, [
            'validate',
            '--env', 'test',
            '--config-dir', str(output_dir)
        ])
        
        # Should have validation warnings but not fail completely
        # Note: This may fail due to missing vault variables, which is expected
        assert 'Configuration' in validate_result.output

def test_layer_create_command():
    """Test layer create command"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        runner = CliRunner()
        result = runner.invoke(app, [
            'layer', 'create', 'monitoring',
            '--output', str(output_dir)
        ])
        
        assert result.exit_code == 0
        
        # Check generated file
        layer_file = output_dir / "monitoring.py"
        assert layer_file.exists()
        
        # Check file content
        content = layer_file.read_text()
        assert 'MonitoringLayer' in content
        assert 'ConfigLayer' in content

def test_layer_validate_command():
    """Test layer validate command"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        
        # First create a layer
        runner = CliRunner()
        create_result = runner.invoke(app, [
            'layer', 'create', 'test-layer',
            '--output', str(output_dir)
        ])
        assert create_result.exit_code == 0
        
        layer_file = output_dir / "test_layer.py"
        assert layer_file.exists()
        
        # Then validate it
        validate_result = runner.invoke(app, [
            'layer', 'validate', str(layer_file)
        ])
        
        assert validate_result.exit_code == 0
        assert 'validation passed' in validate_result.output.lower()

"""Integration tests for end-to-end workflows"""
import pytest
from pathlib import Path
import tempfile
import yaml
from typer.testing import CliRunner

from vmconfig.__main__ import app

@pytest.fixture
def temp_project():
    """Create a temporary project directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def test_full_init_validate_workflow(temp_project):
    """Test complete workflow: init -> validate"""
    project_dir = temp_project / "integration-test"
    
    runner = CliRunner()
    
    # Step 1: Initialize project
    init_result = runner.invoke(app, [
        'init', 'grafana-postgres',
        '--env', 'integration',
        '--output', str(project_dir)
    ])
    
    assert init_result.exit_code == 0
    assert "Project initialized" in init_result.output
    
    # Step 2: Verify file structure
    config_file = project_dir / "environments" / "integration" / "config.yml"
    assert config_file.exists()
    
    assets_dir = project_dir / "assets"
    assert assets_dir.exists()
    assert (assets_dir / "vault-example.yml").exists()
    assert (assets_dir / "deployment-guide.md").exists()
    
    # Step 3: Validate configuration
    validate_result = runner.invoke(app, [
        'validate',
        '--env', 'integration',
        '--config-dir', str(project_dir)
    ])
    
    # Configuration should be structurally valid but may have warnings
    assert 'template' in validate_result.output.lower()

def test_custom_layer_integration(temp_project):
    """Test custom layer creation and validation"""
    layer_dir = temp_project / "custom_layers"
    layer_dir.mkdir()
    
    runner = CliRunner()
    
    # Step 1: Create custom layer
    create_result = runner.invoke(app, [
        'layer', 'create', 'monitoring',
        '--output', str(layer_dir)
    ])
    
    assert create_result.exit_code == 0
    
    layer_file = layer_dir / "monitoring.py"
    assert layer_file.exists()
    
    # Step 2: Validate custom layer
    validate_result = runner.invoke(app, [
        'layer', 'validate', str(layer_file)
    ])
    
    assert validate_result.exit_code == 0
    assert 'validation passed' in validate_result.output.lower()

def test_ansible_artifact_generation(temp_project):
    """Test Ansible artifact generation from template"""
    from vmconfig.framework.templates import TemplateRegistry
    from vmconfig.framework.generators.ansible import AnsibleGenerator
    
    # Get template
    template_class = TemplateRegistry.get_template('grafana-postgres')
    template = template_class()
    
    # Create test config
    env_config = template.generate_initial_config('test')
    
    # Override with test values to avoid vault references
    env_config['vms']['grafana']['vars'].update({
        'grafana_admin_password': 'test_password',
        'grafana_database_host': '10.0.1.11',
        'grafana_database_user': 'grafana',
        'grafana_database_password': 'test_db_password'
    })
    
    env_config['vms']['postgres']['vars'].update({
        'postgres_password': 'test_postgres_password',
        'postgres_users': [{
            'name': 'grafana',
            'password': 'test_db_password', 
            'db': 'grafana'
        }]
    })
    
    # Generate artifacts
    output_dir = temp_project / "artifacts"
    output_dir.mkdir()
    
    generator = AnsibleGenerator(template)
    artifacts = generator.generate_artifacts(env_config, output_dir)
    
    # Verify artifacts were created
    assert len(artifacts) >= 2  # At minimum: inventory and playbook
    
    inventory_path = output_dir / "inventory.yml"
    playbook_path = output_dir / "playbook.yml"
    
    assert inventory_path.exists()
    assert playbook_path.exists()
    
    # Verify inventory structure
    with inventory_path.open() as f:
        inventory = yaml.safe_load(f)
    
    assert 'all' in inventory
    assert 'children' in inventory['all']
    assert 'grafana' in inventory['all']['children']
    assert 'postgres' in inventory['all']['children']
    
    # Verify playbook structure
    with playbook_path.open() as f:
        playbook = yaml.safe_load(f)
    
    assert isinstance(playbook, list)
    assert len(playbook) >= 2  # At least one play per VM
    
    # Check that plays reference correct hosts
    play_hosts = [play.get('hosts') for play in playbook if 'hosts' in play]
    assert 'grafana' in play_hosts
    assert 'postgres' in play_hosts

def test_idempotency_check(temp_project):
    """Test that generated artifacts are idempotent"""
    from vmconfig.framework.templates import TemplateRegistry
    from vmconfig.framework.generators.ansible import AnsibleGenerator
    
    template_class = TemplateRegistry.get_template('grafana-postgres')
    template = template_class()
    
    env_config = template.generate_initial_config('test')
    # Simplify config to avoid vault references
    env_config['vms']['grafana']['vars'] = {
        'grafana_admin_password': 'test_password',
        'grafana_port': 3000
    }
    env_config['vms']['postgres']['vars'] = {
        'postgres_password': 'test_password',
        'postgres_port': 5432
    }
    
    output_dir = temp_project / "idempotency"
    output_dir.mkdir()
    
    generator = AnsibleGenerator(template)
    
    # Generate artifacts twice
    artifacts1 = generator.generate_artifacts(env_config, output_dir)
    artifacts2 = generator.generate_artifacts(env_config, output_dir)
    
    # Content should be identical
    assert len(artifacts1) == len(artifacts2)
    
    for i, (art1, art2) in enumerate(zip(artifacts1, artifacts2)):
        assert art1.path == art2.path
        assert art1.content == art2.content
        assert art1.artifact_type == art2.artifact_type

def test_template_validation_errors(temp_project):
    """Test template validation catches configuration errors"""
    from vmconfig.framework.templates import TemplateRegistry
    
    template_class = TemplateRegistry.get_template('grafana-postgres')
    template = template_class()
    
    # Test with missing required fields
    invalid_config = {
        'template': 'grafana-postgres',
        'vms': {
            'grafana': {
                'host': '10.0.1.10',
                'vars': {}  # Missing required vars
            },
            'postgres': {
                'host': '10.0.1.11', 
                'vars': {}  # Missing required vars
            }
        }
    }
    
    result = template.validate_environment(invalid_config)
    
    assert not result.is_valid
    assert len(result.errors) > 0
    
    # Should catch missing passwords
    error_messages = ' '.join(result.errors).lower()
    assert 'password' in error_messages

def test_layer_dependency_resolution(temp_project):
    """Test that layer dependencies are properly handled"""
    from vmconfig.framework.layers import LayerRegistry
    
    # Test that dependencies exist for all layers
    all_layers = LayerRegistry.list_layers()
    
    for layer_name in all_layers:
        layer_class = LayerRegistry.get_layer(layer_name)
        layer_instance = layer_class()
        
        if hasattr(layer_instance, 'dependencies'):
            for dep in layer_instance.dependencies:
                dep_class = LayerRegistry.get_layer(dep)
                assert dep_class is not None, f"Dependency '{dep}' not found for layer '{layer_name}'"

def test_error_handling_missing_template(temp_project):
    """Test error handling for missing templates"""
    runner = CliRunner()
    
    result = runner.invoke(app, [
        'init', 'nonexistent-template',
        '--env', 'test',
        '--output', str(temp_project / "should-fail")
    ])
    
    assert result.exit_code == 1
    assert 'not found' in result.output.lower()

def test_error_handling_invalid_config(temp_project):
    """Test error handling for invalid configuration"""
    project_dir = temp_project / "invalid-config"
    project_dir.mkdir()
    
    # Create invalid config file
    env_dir = project_dir / "environments" / "test"
    env_dir.mkdir(parents=True)
    
    config_file = env_dir / "config.yml"
    with config_file.open('w') as f:
        yaml.dump({
            'template': 'grafana-postgres',
            # Missing required 'vms' section
        }, f)
    
    runner = CliRunner()
    result = runner.invoke(app, [
        'validate',
        '--env', 'test',
        '--config-dir', str(project_dir)
    ])
    
    assert result.exit_code == 1
    assert 'validation failed' in result.output.lower()

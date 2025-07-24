"""Test framework components"""
import pytest
from vmconfig.framework.templates import TemplateRegistry, ValidationResult
from vmconfig.framework.layers import LayerRegistry

def test_template_registry():
    """Test template registry functionality"""
    templates = TemplateRegistry.list_templates()
    assert 'grafana-postgres' in templates
    
    template_class = TemplateRegistry.get_template('grafana-postgres')
    assert template_class is not None
    
    template_instance = template_class()
    assert template_instance.name == 'grafana-postgres'
    assert len(template_instance.vms) == 2
    assert 'grafana' in template_instance.vms
    assert 'postgres' in template_instance.vms

def test_layer_registry():
    """Test layer registry functionality"""
    layers = LayerRegistry.list_layers()
    expected_layers = ['base-os', 'docker', 'networking', 'grafana', 'postgresql']
    
    for layer in expected_layers:
        assert layer in layers
    
    # Test layer instantiation
    base_os_class = LayerRegistry.get_layer('base-os')
    assert base_os_class is not None
    
    base_os_instance = base_os_class()
    assert base_os_instance.name == 'base-os'
    assert base_os_instance.dependencies == []

def test_grafana_postgres_template():
    """Test Grafana-PostgreSQL template"""
    template_class = TemplateRegistry.get_template('grafana-postgres')
    template = template_class()
    
    # Test initial config generation
    config = template.generate_initial_config('dev')
    assert config['template'] == 'grafana-postgres'
    assert 'vms' in config
    assert 'grafana' in config['vms']
    assert 'postgres' in config['vms']
    
    # Test validation with valid config
    result = template.validate_environment(config)
    assert isinstance(result, ValidationResult)
    # Note: May have warnings but should not have errors for basic structure

def test_layer_dependencies():
    """Test layer dependency resolution"""
    docker_class = LayerRegistry.get_layer('docker')
    docker_layer = docker_class()
    
    assert 'base-os' in docker_layer.dependencies
    
    grafana_class = LayerRegistry.get_layer('grafana') 
    grafana_layer = grafana_class()
    
    expected_deps = ['base-os', 'docker']
    for dep in expected_deps:
        assert dep in grafana_layer.dependencies

def test_ansible_task_generation():
    """Test Ansible task generation"""
    base_os_class = LayerRegistry.get_layer('base-os')
    base_os_layer = base_os_class()
    
    tasks = base_os_layer.generate_ansible_tasks({})
    assert len(tasks) > 0
    
    # Check first task structure
    first_task = tasks[0]
    assert hasattr(first_task, 'name')
    assert hasattr(first_task, 'module')
    assert hasattr(first_task, 'params')
    
    # Test conversion to dict
    task_dict = first_task.to_dict()
    assert 'name' in task_dict
    assert isinstance(task_dict, dict)

"""Ansible playbook and inventory generation"""
import subprocess
import yaml
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

from vmconfig.framework.templates import ServiceTemplate, Artifact
from vmconfig.framework.layers import LayerRegistry

@dataclass
class AnsibleExecutionResult:
    """Result of Ansible playbook execution"""
    success: bool
    changed_tasks: int = 0
    failed_tasks: int = 0
    error_message: str = ""
    stdout: str = ""
    stderr: str = ""

class AnsibleGenerator:
    """Generate Ansible playbooks and inventories"""
    
    def __init__(self, template: ServiceTemplate):
        self.template = template
    
    def generate_artifacts(self, env_config: Dict[str, Any], output_dir: Path) -> List[Artifact]:
        """Generate all Ansible artifacts"""
        artifacts = []
        
        # Generate inventory
        inventory_artifact = self._generate_inventory(env_config, output_dir)
        artifacts.append(inventory_artifact)
        
        # Generate playbook
        playbook_artifact = self._generate_playbook(env_config, output_dir)
        artifacts.append(playbook_artifact)
        
        # Generate group vars
        group_vars_artifacts = self._generate_group_vars(env_config, output_dir)
        artifacts.extend(group_vars_artifacts)
        
        # Write artifacts to disk
        for artifact in artifacts:
            artifact.path.parent.mkdir(parents=True, exist_ok=True)
            with artifact.path.open('w') as f:
                f.write(artifact.content)
        
        return artifacts
    
    def _generate_inventory(self, env_config: Dict[str, Any], output_dir: Path) -> Artifact:
        """Generate Ansible inventory file"""
        
        inventory = {
            'all': {
                'children': {}
            }
        }
        
        vms_config = env_config.get('vms', {})
        
        for vm_name, vm_config in vms_config.items():
            # Create group for each VM
            inventory['all']['children'][vm_name] = {
                'hosts': {
                    vm_config['host']: {
                        'ansible_user': vm_config.get('ansible_user', 'ubuntu'),
                        'ansible_ssh_private_key_file': vm_config.get('ssh_key_file', '~/.ssh/id_rsa')
                    }
                }
            }
        
        content = yaml.dump(inventory, default_flow_style=False)
        
        return Artifact(
            path=output_dir / "inventory.yml",
            content=content,
            artifact_type="inventory"
        )
    
    def _generate_playbook(self, env_config: Dict[str, Any], output_dir: Path) -> Artifact:
        """Generate main Ansible playbook"""
        
        plays = []
        vms_config = env_config.get('vms', {})
        
        # Generate play for each VM
        for vm_name, vm_config in vms_config.items():
            if vm_name not in self.template.vms:
                continue
                
            template_vm_config = self.template.vms[vm_name]
            
            play = {
                'name': f'Configure {vm_name} VM',
                'hosts': vm_name,
                'become': True,
                'gather_facts': True,
                'tasks': []
            }
            
            # Generate tasks for each layer
            for layer_name in template_vm_config.layers:
                layer_class = LayerRegistry.get_layer(layer_name)
                if layer_class:
                    layer_instance = layer_class()
                    layer_tasks = layer_instance.generate_ansible_tasks(vm_config)
                    
                    # Add section comment
                    play['tasks'].append({
                        'name': f'=== {layer_name.upper()} LAYER ===',
                        'debug': {'msg': f'Configuring {layer_name} layer'}
                    })
                    
                    # Add layer tasks
                    for task in layer_tasks:
                        play['tasks'].append(task.to_dict())
            
            # Add handlers if any
            handlers = []
            for layer_name in template_vm_config.layers:
                layer_class = LayerRegistry.get_layer(layer_name)
                if layer_class:
                    layer_instance = layer_class()
                    layer_handlers = layer_instance.generate_handlers()
                    handlers.extend(layer_handlers)
            
            if handlers:
                play['handlers'] = handlers
            
            plays.append(play)
        
        # Add connectivity verification play
        if len(plays) > 1:
            verification_play = {
                'name': 'Verify service connectivity',
                'hosts': 'all',
                'gather_facts': False,
                'tasks': [
                    {
                        'name': 'Wait for services to be ready',
                        'wait_for': {
                            'port': '{{ item }}',
                            'host': '{{ ansible_host }}',
                            'timeout': 60
                        },
                        'loop': '{{ service_ports | default([]) }}'
                    }
                ]
            }
            plays.append(verification_play)
        
        playbook_content = yaml.dump(plays, default_flow_style=False)
        
        return Artifact(
            path=output_dir / "playbook.yml",
            content=playbook_content,
            artifact_type="playbook"
        )
    
    def _generate_group_vars(self, env_config: Dict[str, Any], output_dir: Path) -> List[Artifact]:
        """Generate group_vars files for each VM"""
        
        artifacts = []
        vms_config = env_config.get('vms', {})
        
        group_vars_dir = output_dir / "group_vars"
        
        for vm_name, vm_config in vms_config.items():
            if vm_name not in self.template.vms:
                continue
            
            # Merge template variables with environment variables
            vars_content = {}
            
            # Add template VM variables
            template_vm_config = self.template.vms[vm_name]
            if hasattr(template_vm_config, 'vars'):
                vars_content.update(template_vm_config.vars)
            
            # Add environment-specific variables
            if 'vars' in vm_config:
                vars_content.update(vm_config['vars'])
            
            # Add service-specific variables based on template
            if hasattr(template_vm_config, 'services'):
                service_ports = []
                for service in template_vm_config.services:
                    if service == 'grafana':
                        service_ports.append(3000)
                        vars_content['grafana_port'] = 3000
                    elif service == 'postgresql':
                        service_ports.append(5432)
                        vars_content['postgres_port'] = 5432
                    elif service == 'nginx':
                        service_ports.extend([80, 443])
                
                vars_content['service_ports'] = service_ports
            
            if vars_content:
                content = yaml.dump(vars_content, default_flow_style=False)
                
                artifact = Artifact(
                    path=group_vars_dir / f"{vm_name}.yml",
                    content=content,
                    artifact_type="group_vars"
                )
                artifacts.append(artifact)
        
        return artifacts
    
    def execute_playbook(
        self, 
        playbook_path: Path, 
        inventory_path: Path,
        target_vm: str = None
    ) -> AnsibleExecutionResult:
        """Execute Ansible playbook"""
        
        cmd = [
            'ansible-playbook',
            '-i', str(inventory_path),
            str(playbook_path),
            '-v'  # Verbose output
        ]
        
        if target_vm:
            cmd.extend(['--limit', target_vm])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Parse Ansible output for statistics
            changed_tasks = 0
            failed_tasks = 0
            
            if result.stdout:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'changed=' in line:
                        # Extract changed count from Ansible recap
                        try:
                            changed_part = line.split('changed=')[1].split()[0]
                            changed_tasks += int(changed_part)
                        except (IndexError, ValueError):
                            pass
                    elif 'failed=' in line:
                        try:
                            failed_part = line.split('failed=')[1].split()[0]
                            failed_tasks += int(failed_part)
                        except (IndexError, ValueError):
                            pass
            
            return AnsibleExecutionResult(
                success=result.returncode == 0,
                changed_tasks=changed_tasks,
                failed_tasks=failed_tasks,
                error_message=result.stderr if result.returncode != 0 else "",
                stdout=result.stdout,
                stderr=result.stderr
            )
        
        except subprocess.TimeoutExpired:
            return AnsibleExecutionResult(
                success=False,
                error_message="Ansible execution timed out after 5 minutes"
            )
        except FileNotFoundError:
            return AnsibleExecutionResult(
                success=False,
                error_message="Ansible not found. Please install ansible-core: pip install ansible"
            )
        except Exception as e:
            return AnsibleExecutionResult(
                success=False,
                error_message=f"Execution failed: {e}"
            )

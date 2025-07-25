"""Ansible playbook and inventory generation"""
import subprocess
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import re

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
    
    def generate_artifacts(self, env_config: Dict[str, Any], output_dir: Path, vault_file: Optional[str] = None) -> List[Artifact]:
        """Generate all Ansible artifacts"""
        artifacts = []
        
        # Generate ansible.cfg
        ansible_cfg_artifact = self._generate_ansible_cfg(output_dir)
        artifacts.append(ansible_cfg_artifact)

        # Generate inventory
        inventory_artifact = self._generate_inventory(env_config, output_dir)
        artifacts.append(inventory_artifact)
        
        # Generate playbook
        playbook_artifact = self._generate_playbook(env_config, output_dir, vault_file=vault_file)
        artifacts.append(playbook_artifact)
        
        # Generate host vars
        host_vars_artifacts = self._generate_host_vars(env_config, output_dir)
        artifacts.extend(host_vars_artifacts)
        
        # Write artifacts to disk
        for artifact in artifacts:
            artifact.path.parent.mkdir(parents=True, exist_ok=True)
            with artifact.path.open('w') as f:
                f.write(artifact.content)
        
        return artifacts

    def _generate_ansible_cfg(self, output_dir: Path) -> Artifact:
        """Generate ansible.cfg file"""
        content = """[defaults]
inventory = inventory.yml
host_key_checking = False
retry_files_enabled = False
deprecation_warnings = False

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
"""
        return Artifact(
            path=output_dir / "ansible.cfg",
            content=content,
            artifact_type="ansible_cfg"
        )
    
    def _generate_inventory(self, env_config: Dict[str, Any], output_dir: Path) -> Artifact:
        """Generate Ansible inventory file"""
        
        inventory = {
            'all': {
                'hosts': {}
            }
        }
        
        vms_config = env_config.get('vms', {})
        
        for vm_name, vm_config in vms_config.items():
            host_entry = {
                'ansible_user': vm_config.get('ansible_user', 'ubuntu')
            }
            if vm_config.get('ssh_key_file'):
                host_entry['ansible_ssh_private_key_file'] = vm_config['ssh_key_file']
            
            # Handle SSH alias resolution
            inventory_hostname = vm_config.get('host', vm_name)
            
            # If we have an actual hostname resolved from SSH config, use it for ansible_host
            if vm_config.get('actual_hostname'):
                host_entry['ansible_host'] = vm_config['actual_hostname']
            elif vm_config.get('ansible_host'):
                host_entry['ansible_host'] = vm_config['ansible_host']

            inventory['all']['hosts'][inventory_hostname] = host_entry
        
        content = yaml.dump(inventory, default_flow_style=False)
        
        return Artifact(
            path=output_dir / "inventory.yml",
            content=content,
            artifact_type="inventory"
        )
    
    def _generate_playbook(self, env_config: Dict[str, Any], output_dir: Path, vault_file: Optional[str] = None) -> Artifact:
        """Generate main Ansible playbook"""
        
        plays = []
        vms_config = env_config.get('vms', {})
        vm_names = list(vms_config.keys())

        # Build dependency graph for topological sort
        adj = {vm: [] for vm in vm_names}
        in_degree = {vm: 0 for vm in vm_names}

        # Create hostname to VM name mapping
        hostname_to_vm = {}
        for vm_name, vm_config in vms_config.items():
            hostname = vm_config.get('host', vm_name)
            hostname_to_vm[hostname] = vm_name

        for vm_name in vm_names:
            vm_vars = vms_config[vm_name].get('vars', {})
            vars_str = yaml.dump(vm_vars)
            
            for other_vm in vm_names:
                if vm_name == other_vm:
                    continue
                
                # Check for template variable references like 'vms.other_vm'
                if f"vms.{other_vm}" in vars_str:
                    adj[other_vm].append(vm_name)
                    in_degree[vm_name] += 1
                    continue
                
                # Check for hostname references
                other_hostname = vms_config[other_vm].get('host', other_vm)
                if other_hostname in vars_str:
                    # Additional validation: ensure it's actually a dependency, not just a coincidental match
                    # Look for database, host, or service references
                    dependency_indicators = [
                        f"database_host: {other_hostname}",
                        f"database_host: '{other_hostname}'", 
                        f'database_host: "{other_hostname}"',
                        f"host: {other_hostname}",
                        f"host: '{other_hostname}'",
                        f'host: "{other_hostname}"',
                        f"server: {other_hostname}",
                        f"server: '{other_hostname}'",
                        f'server: "{other_hostname}"'
                    ]
                    
                    if any(indicator in vars_str for indicator in dependency_indicators):
                        adj[other_vm].append(vm_name)
                        in_degree[vm_name] += 1
        
        # Topological sort (Kahn's algorithm)
        queue = [vm for vm in vm_names if in_degree[vm] == 0]
        sorted_vm_names = []
        while queue:
            u = queue.pop(0)
            sorted_vm_names.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        
        if len(sorted_vm_names) != len(vm_names):
            # If there's a cycle, we can't sort. Use original order and let Ansible fail.
            sorted_vm_names = vm_names

        # Generate play for each VM
        for vm_name in sorted_vm_names:
            vm_config = vms_config[vm_name]
            if vm_name not in self.template.vms:
                continue
                
            template_vm_config = self.template.vms[vm_name]
            
            inventory_hostname = vm_config.get('host', vm_name)

            play = {
                'name': f'Configure {vm_name} VM',
                'hosts': inventory_hostname,
                'become': True,
                'gather_facts': True,
                'tasks': []
            }
            
            if vault_file:
                play['pre_tasks'] = [{
                    'name': 'Include vault variables',
                    'include_vars': {
                        'file': vault_file,
                        'name': 'vault'
                    }
                }]

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
    
    def _resolve_config_vars(self, value: Any, env_config: Dict[str, Any]) -> Any:
        """Recursively resolve template variables in config values."""
        if isinstance(value, str):
            def replacer(match):
                path = match.group(1).strip()
                parts = path.split('.')
                try:
                    ref_val = env_config
                    for part in parts:
                        ref_val = ref_val[part]
                    return str(ref_val)
                except (KeyError, TypeError, IndexError):
                    return match.group(0) # Return original if not found
            
            return re.sub(r'\{\{\s*(.*?)\s*\}\}', replacer, value)
        elif isinstance(value, dict):
            return {k: self._resolve_config_vars(v, env_config) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_config_vars(item, env_config) for item in value]
        else:
            return value

    def _generate_host_vars(self, env_config: Dict[str, Any], output_dir: Path) -> List[Artifact]:
        """Generate host_vars files for each VM"""
        
        artifacts = []
        vms_config = env_config.get('vms', {})
        
        host_vars_dir = output_dir / "host_vars"
        
        for vm_name, vm_config in vms_config.items():
            if vm_name not in self.template.vms:
                continue
            
            inventory_hostname = vm_config.get('host', vm_name)

            # Merge template variables with environment variables
            vars_content = {}
            
            # Add template VM variables
            template_vm_config = self.template.vms[vm_name]
            if hasattr(template_vm_config, 'vars'):
                vars_content.update(template_vm_config.vars)
            
            # Add environment-specific variables
            if 'vars' in vm_config:
                vars_content.update(self._resolve_config_vars(vm_config['vars'], env_config))
            
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
                        service_ports.append(80)  # Always include HTTP
                        # Only include HTTPS port if SSL is enabled
                        nginx_use_ssl = vars_content.get('nginx_use_ssl', True)
                        grafana_domain = vars_content.get('grafana_domain', '')
                        is_aws_domain = 'amazonaws.com' in grafana_domain or 'compute.internal' in grafana_domain
                        
                        # Use SSL unless it's an AWS domain or explicitly disabled
                        if nginx_use_ssl and not is_aws_domain:
                            service_ports.append(443)
                
                vars_content['service_ports'] = service_ports
            
            if vars_content:
                content = yaml.dump(vars_content, default_flow_style=False)
                
                artifact = Artifact(
                    path=host_vars_dir / f"{inventory_hostname}.yml",
                    content=content,
                    artifact_type="host_vars"
                )
                artifacts.append(artifact)
        
        return artifacts
    
    def execute_playbook(
        self,
        playbook_path: Path,
        inventory_path: Path,
        target_vm: str = None,
        use_vault: bool = False,
        cwd: Optional[Path] = None,
    ) -> AnsibleExecutionResult:
        """Execute Ansible playbook"""

        cmd = [
            "ansible-playbook",
            "-i",
            str(inventory_path),
            str(playbook_path),
            "-v",  # Verbose output
        ]

        if use_vault:
            cmd.append("--ask-vault-pass")

        if target_vm:
            cmd.extend(["--limit", target_vm])

        try:
            capture = not use_vault
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=cwd,
            )

            # Parse Ansible output for statistics
            changed_tasks = 0
            failed_tasks = 0

            stdout_data = result.stdout if capture else ""
            if stdout_data:
                lines = stdout_data.split("\n")
                for line in lines:
                    if "changed=" in line:
                        # Extract changed count from Ansible recap
                        try:
                            changed_part = line.split("changed=")[1].split()[0]
                            changed_tasks += int(changed_part)
                        except (IndexError, ValueError):
                            pass
                    elif "failed=" in line:
                        try:
                            failed_part = line.split("failed=")[1].split()[0]
                            failed_tasks += int(failed_part)
                        except (IndexError, ValueError):
                            pass
            
            error_message = ""
            if result.returncode != 0:
                if capture:
                    error_message = result.stdout
                else:
                    error_message = "Ansible execution failed. See output above for details."


            return AnsibleExecutionResult(
                success=result.returncode == 0,
                changed_tasks=changed_tasks,
                failed_tasks=failed_tasks,
                error_message=error_message,
                stdout=stdout_data,
                stderr=result.stderr if capture else "",
            )

        except subprocess.TimeoutExpired:
            return AnsibleExecutionResult(
                success=False,
                error_message="Ansible execution timed out after 5 minutes",
            )
        except FileNotFoundError:
            return AnsibleExecutionResult(
                success=False,
                error_message="Ansible not found. Please install ansible-core: pip install ansible",
            )
        except Exception as e:
            return AnsibleExecutionResult(success=False, error_message=f"Execution failed: {e}")

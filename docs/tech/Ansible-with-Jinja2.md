Ansible in the VM-Config-Factory project
========================================

Purpose  
The CLI command

```bash
vm-config apply --env dev
```

does three things:

1. Generates all Ansible artefacts for the chosen environment ( `environments/dev/` )  
   - ansible.cfg  
   - inventory.yml  
   - playbook.yml  
   - host_vars/\*.yml  
   - templates/\*  (static and Jinja2 files)
2. Runs `ansible-playbook` on the generated playbook.
3. Recaps success / failure.

Directory layout after generation

```
environments/dev/
├── ansible.cfg
├── inventory.yml
├── playbook.yml
├── host_vars/
│   ├── grafana.yml
│   └── grafana-db.yml
└── templates/
    ├── grafana-nginx.conf.j2
    └── ...
```

How artefacts are produced  
The Python generator (`AnsibleGenerator`) reads `environment.yml` plus the
selected template (e.g. *grafana-postgres*).  
For each VM it inspects the configured “layers” (base-os, docker, application,
networking…) and emits the corresponding tasks and handlers.

Example snippet from the rendered playbook

```yaml
- name: Configure grafana VM
  hosts: grafana
  become: true
  gather_facts: true

  pre_tasks:
    - name: Include vault variables
      include_vars:
        file: vault-dev.yml
        name: vault

  tasks:
    - name: === GRAFANA LAYER ===
      debug:
        msg: Configuring grafana layer

    - name: Allow Grafana port through firewall
      ufw:
        port: "{{ grafana_port | default(3000) }}"
        proto: tcp
        rule: allow
```

Variable flow & precedence
--------------------------

Highest to lowest:

1. Extra-vars (`--extra-vars` when you call Ansible manually)
2. `host_vars/<inventory_hostname>.yml`
3. Variables defined inside `playbook.yml`
4. Defaults inside roles / layers
5. Built-ins (`ansible_user`, `ansible_host`, …)

The generator fills `host_vars/\*.yml` with:

```yaml
grafana_port: 3000
postgres_port: 5432
service_ports:
  - 3000
  - 80
  - 443
```

Secrets  
Vaulted values live in `vault-dev.yml` and are imported by a
`pre_tasks → include_vars` step.  
You will be prompted for the vault password during `vm-config apply` unless
you disable `--ask-vault-pass`.

Jinja2 templating
-----------------

Why?  
Many configuration files (Nginx, Grafana ini, systemd service files, …) need
per-environment values (ports, domains, passwords). Writing one static file
per environment is error-prone; instead we keep a **single** template with
place-holders that Ansible renders at deploy time.

Naming convention  
Files that require rendering are saved in `templates/` with a
`.j2` extension, e.g. `grafana-nginx.conf.j2`. The extension is only a hint
for humans; Ansible renders any file passed to the `template` module.

Example template (`templates/grafana-nginx.conf.j2`)

```nginx
server {
    listen 80;
    server_name {{ grafana_domain }};

    location / {
        proxy_pass http://127.0.0.1:{{ grafana_port }};
        include proxy_params;
    }
}
```

Task that deploys it

```yaml
- name: Deploy Grafana Nginx site
  template:
    src: grafana-nginx.conf.j2   # looked up in templates/
    dest: /etc/nginx/sites-available/grafana
    mode: "0644"
  notify: reload nginx
```

At runtime Ansible substitutes:

- `{{ grafana_domain }}` → from vault or host_vars (`grafana.example.com`)
- `{{ grafana_port }}`   → `3000`

Static files  
If a file needs **no** variable replacement, use the `copy` module instead of
`template`:

```yaml
- name: Ship static proxy parameters
  copy:
    src: proxy.conf          # inside templates/ or a relative path
    dest: /etc/nginx/conf.d/proxy.conf
    mode: "0644"
```

Common pitfalls & troubleshooting
---------------------------------

- **“conflicting action statements”**  
  A task may only contain one action key (the module name).  
  Fix:

  ```yaml
  - name: restart postgres
    community.docker.docker_compose_v2:
      project_src: /opt/postgres
      recreate: always
      state: present
  ```

- **“Could not find or access '…'”**  
  The `template` module did not locate the file. Ensure the file is inside
  `templates/` or give the correct relative/absolute path.

- **Forgot `.j2` extension**  
  Ansible will still render the file, but teammates may assume it is static.
  Prefer explicit `.j2` for clarity.

- **Variable not substituted**  
  Check precedence. A missing variable renders as an empty string unless
  `{{ variable | default('value') }}` is used.

Recap workflow
--------------

1. Edit `environments/<env>/config.yml` and any templates under
   `templates/`.
2. Encrypt/adjust `vault-<env>.yml` for secrets.
3. Run

   ```bash
   vm-config apply --env <env>
   ```

4. Inspect generated artefacts if something fails.
5. Repeat until playbook completes with zero failed tasks.

By leveraging Ansible plus Jinja2 templates, the VM-Config-Factory delivers a
repeatable, parameterised infrastructure provisioning flow that is easy to
audit and extend.
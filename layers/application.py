"""Application layers for Grafana and PostgreSQL"""
from typing import Dict, List, Any
from vmconfig.framework.layers import ConfigLayer, AnsibleTask

class GrafanaLayer(ConfigLayer):
    """Grafana application configuration"""
    
    name = "grafana"
    description = "Grafana monitoring and visualization platform"
    dependencies = ["base-os", "docker"]
    
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate Grafana configuration tasks"""
        tasks = [
            AnsibleTask(
                name="Create grafana directories",
                module="file",
                params={
                    "path": "{{ item }}",
                    "state": "directory",
                    "mode": "0755",
                    "owner": "472",  # Grafana user ID in container
                    "group": "472"
                }
            ),
            AnsibleTask(
                name="Set grafana directories",
                module="set_fact",
                params={
                    "grafana_dirs": [
                        "/opt/grafana/data",
                        "/opt/grafana/config",
                        "/opt/grafana/logs"
                    ]
                }
            ),
            AnsibleTask(
                name="Create Grafana docker-compose file",
                module="copy",
                params={
                    "content": '''version: '3.8'
services:
  grafana:
    image: grafana/grafana:{{ grafana_version | default('latest') }}
    container_name: grafana
    restart: unless-stopped
    ports:
      - "{{ grafana_port | default(3000) }}:3000"
    volumes:
      - /opt/grafana/data:/var/lib/grafana
      - /opt/grafana/logs:/var/log/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD={{ grafana_admin_password }}
      - GF_DATABASE_TYPE=postgres
      - GF_DATABASE_HOST={{ grafana_database_host }}
      - GF_DATABASE_NAME={{ grafana_database_name | default('grafana') }}
      - GF_DATABASE_USER={{ grafana_database_user }}
      - GF_DATABASE_PASSWORD={{ grafana_database_password }}
    networks:
      - grafana_network

networks:
  grafana_network:
    driver: bridge
''',
                    "dest": "/opt/grafana/docker-compose.yml",
                    "mode": "0644"
                }
            ),
            AnsibleTask(
                name="Start Grafana container",
                module="docker_compose",
                params={
                    "project_src": "/opt/grafana",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Wait for Grafana to be ready",
                module="uri",
                params={
                    "url": "http://localhost:{{ grafana_port | default(3000) }}/api/health",
                    "method": "GET",
                    "status_code": 200
                },
                retries=30,
                delay=5
            )
        ]
        
        return tasks
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate handlers for Grafana layer"""
        return [
            {
                "name": "restart grafana",
                "docker_compose": {
                    "project_src": "/opt/grafana",
                    "restarted": True
                }
            }
        ]
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate Grafana management scripts"""
        return {
            "grafana-status.sh": """#!/bin/bash
# Grafana status script
echo "=== Grafana Container Status ==="
docker ps | grep grafana
echo ""
echo "=== Grafana Health Check ==="
curl -s http://localhost:3000/api/health | python3 -m json.tool
echo ""
echo "=== Grafana Logs (last 20 lines) ==="
docker logs --tail=20 grafana
""",
            "grafana-backup.sh": """#!/bin/bash
# Grafana backup script
BACKUP_DIR="/opt/backups/grafana"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "Creating Grafana backup..."
docker exec grafana tar czf - /var/lib/grafana > $BACKUP_DIR/grafana_data_$TIMESTAMP.tar.gz
echo "Backup created: $BACKUP_DIR/grafana_data_$TIMESTAMP.tar.gz"
""",
            "grafana-restore.sh": """#!/bin/bash
# Grafana restore script
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Available backups:"
    ls -la /opt/backups/grafana/
    exit 1
fi

BACKUP_FILE=$1
echo "Stopping Grafana..."
docker-compose -f /opt/grafana/docker-compose.yml down

echo "Restoring from $BACKUP_FILE..."
docker run --rm -v grafana_data:/var/lib/grafana -v $(dirname $BACKUP_FILE):/backup alpine tar xzf /backup/$(basename $BACKUP_FILE) -C /

echo "Starting Grafana..."
docker-compose -f /opt/grafana/docker-compose.yml up -d
"""
        }

class PostgreSQLLayer(ConfigLayer):
    """PostgreSQL database configuration"""
    
    name = "postgresql"
    description = "PostgreSQL database server"
    dependencies = ["base-os", "docker"]
    
    def generate_ansible_tasks(self, vm_config: Dict[str, Any]) -> List[AnsibleTask]:
        """Generate PostgreSQL configuration tasks"""
        tasks = [
            AnsibleTask(
                name="Create PostgreSQL directories",
                module="file",
                params={
                    "path": "{{ item }}",
                    "state": "directory",
                    "mode": "0755"
                }
            ),
            AnsibleTask(
                name="Set PostgreSQL directories",
                module="set_fact",
                params={
                    "postgres_dirs": [
                        "/opt/postgres/data",
                        "/opt/postgres/config",
                        "/opt/postgres/logs",
                        "/opt/backups/postgres"
                    ]
                }
            ),
            AnsibleTask(
                name="Create PostgreSQL configuration",
                module="copy",
                params={
                    "content": '''# PostgreSQL configuration
listen_addresses = '*'
port = 5432
max_connections = 100
shared_buffers = 128MB
effective_cache_size = 256MB
work_mem = 4MB
maintenance_work_mem = 64MB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_messages = info
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

# Security
ssl = off
''',
                    "dest": "/opt/postgres/config/postgresql.conf",
                    "mode": "0644"
                }
            ),
            AnsibleTask(
                name="Create PostgreSQL host-based authentication",
                module="copy",
                params={
                    "content": '''# Host-based authentication file
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             10.0.0.0/8              md5
host    all             all             172.16.0.0/12           md5
host    all             all             192.168.0.0/16          md5
''',
                    "dest": "/opt/postgres/config/pg_hba.conf",
                    "mode": "0644"
                }
            ),
            AnsibleTask(
                name="Create PostgreSQL docker-compose file",
                module="copy",
                params={
                    "content": '''version: '3.8'
services:
  postgres:
    image: postgres:{{ postgres_version | default('15') }}
    container_name: postgres
    restart: unless-stopped
    ports:
      - "{{ postgres_port | default(5432) }}:5432"
    volumes:
      - /opt/postgres/data:/var/lib/postgresql/data
      - /opt/postgres/config/postgresql.conf:/etc/postgresql/postgresql.conf
      - /opt/postgres/config/pg_hba.conf:/etc/postgresql/pg_hba.conf
      - /opt/postgres/logs:/var/log/postgresql
    environment:
      - POSTGRES_PASSWORD={{ postgres_password }}
      - POSTGRES_DB={{ postgres_default_db | default('postgres') }}
      - PGDATA=/var/lib/postgresql/data/pgdata
    command: >
      postgres
      -c config_file=/etc/postgresql/postgresql.conf
      -c hba_file=/etc/postgresql/pg_hba.conf
    networks:
      - postgres_network

networks:
  postgres_network:
    driver: bridge
''',
                    "dest": "/opt/postgres/docker-compose.yml",
                    "mode": "0644"
                }
            ),
            AnsibleTask(
                name="Start PostgreSQL container",
                module="docker_compose",
                params={
                    "project_src": "/opt/postgres",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Wait for PostgreSQL to be ready",
                module="postgresql_ping",
                params={
                    "db": "postgres",
                    "login_host": "localhost",
                    "login_user": "postgres",
                    "login_password": "{{ postgres_password }}"
                },
                retries=30,
                delay=5
            ),
            AnsibleTask(
                name="Create application databases",
                module="postgresql_db",
                params={
                    "name": "{{ item }}",
                    "login_host": "localhost",
                    "login_user": "postgres",
                    "login_password": "{{ postgres_password }}",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Set application databases",
                module="set_fact",
                params={
                    "postgres_databases": "{{ postgres_databases | default(['grafana']) }}"
                }
            ),
            AnsibleTask(
                name="Create application users",
                module="postgresql_user",
                params={
                    "name": "{{ item.name }}",
                    "password": "{{ item.password }}",
                    "db": "{{ item.db }}",
                    "login_host": "localhost",
                    "login_user": "postgres",
                    "login_password": "{{ postgres_password }}",
                    "priv": "ALL",
                    "state": "present"
                }
            ),
            AnsibleTask(
                name="Set application users",
                module="set_fact",
                params={
                    "postgres_users": "{{ postgres_users | default([]) }}"
                }
            )
        ]
        
        return tasks
    
    def generate_handlers(self) -> List[Dict[str, Any]]:
        """Generate handlers for PostgreSQL layer"""
        return [
            {
                "name": "restart postgres",
                "docker_compose": {
                    "project_src": "/opt/postgres",
                    "restarted": True
                }
            }
        ]
    
    def generate_scripts(self, vm_config: Dict[str, Any]) -> Dict[str, str]:
        """Generate PostgreSQL management scripts"""
        return {
            "postgres-status.sh": """#!/bin/bash
# PostgreSQL status script
echo "=== PostgreSQL Container Status ==="
docker ps | grep postgres
echo ""
echo "=== PostgreSQL Connection Test ==="
docker exec postgres pg_isready -U postgres
echo ""
echo "=== Database List ==="
docker exec postgres psql -U postgres -c "\\l"
echo ""
echo "=== PostgreSQL Logs (last 20 lines) ==="
docker logs --tail=20 postgres
""",
            "postgres-backup.sh": """#!/bin/bash
# PostgreSQL backup script
BACKUP_DIR="/opt/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

if [ -z "$1" ]; then
    echo "Usage: $0 <database_name>"
    echo "Available databases:"
    docker exec postgres psql -U postgres -c "\\l"
    exit 1
fi

DATABASE=$1
echo "Creating backup for database: $DATABASE"
docker exec postgres pg_dump -U postgres $DATABASE > $BACKUP_DIR/${DATABASE}_$TIMESTAMP.sql
echo "Backup created: $BACKUP_DIR/${DATABASE}_$TIMESTAMP.sql"
""",
            "postgres-restore.sh": """#!/bin/bash
# PostgreSQL restore script
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <database_name> <backup_file>"
    echo "Available backups:"
    ls -la /opt/backups/postgres/
    exit 1
fi

DATABASE=$1
BACKUP_FILE=$2

echo "Restoring database $DATABASE from $BACKUP_FILE..."
docker exec -i postgres psql -U postgres $DATABASE < $BACKUP_FILE
echo "Restore completed"
""",
            "postgres-console.sh": """#!/bin/bash
# PostgreSQL console script
echo "Connecting to PostgreSQL console..."
docker exec -it postgres psql -U postgres
"""
        }

#!/usr/bin/env bash
set -e

read -p "Environment [prod]: " ENV
ENV=${ENV:-prod}
read -p "Project directory [grafana-stack]: " DIR
DIR=${DIR:-grafana-stack}
read -p "Grafana VM host [grafana]: " GRAFANA_HOST
GRAFANA_HOST=${GRAFANA_HOST:-grafana}
read -p "Postgres VM host [grafana-db]: " POSTGRES_HOST
POSTGRES_HOST=${POSTGRES_HOST:-grafana-db}

if ! command -v uv >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    echo "python3 is installed, but uv is not. Install uv to proceed"
    exit 1
  else
    echo "python3 is not installed. Install python3 to proceed"
    exit 1
  fi
fi

uv sync
uv pip install -e .

# add `source .venv/bin/activate` to .zshrc or .zshenv
read -p "Add `source .venv/bin/activate` to .zshrc? [Y/n]: " ACTIVATE
if [ "$ACTIVATE" != "n" ]; then
    file='.zshrc'
    if [ -f ~/.zshenv ]; then
        file='.zshenv'
    fi
    # appending safely to end of file
    echo "source .venv/bin/activate" >> ~/.$file
    source ~/.$file
fi

read -p "Run `vm-config init grafana-postgres --env $ENV --output $DIR`? [Y/n]: " INIT
# if not n, then run the command
if [ "$INIT" == "n" ]; then
    echo "Skipping init"
    exit 0
fi

vm-config init grafana-postgres --env "$ENV" --output "$DIR"
CONFIG_FILE="$DIR/environments/$ENV/config.yml"
uv run -- python - <<PY
import yaml, pathlib
p=pathlib.Path("$CONFIG_FILE")
d=yaml.safe_load(p.read_text())
d['vms']['grafana']['host']="$GRAFANA_HOST"
d['vms']['postgres']['host']="$POSTGRES_HOST"
d['vms']['grafana']['ansible_user']='ubuntu'
d['vms']['postgres']['ansible_user']='ubuntu'
p.write_text(yaml.safe_dump(d))
PY
/usr/bin/time -p $CMD apply --env "$ENV" --config-dir "$DIR"
echo "Running second apply to verify idempotency"
/usr/bin/time -p $CMD apply --env "$ENV" --config-dir "$DIR" | tee /tmp/vmconfig_second_apply.log
grep -q "Changed: 0" /tmp/vmconfig_second_apply.log && echo "Idempotency confirmed" || echo "Tasks changed on rerun" 
Sounds good—splitting the **service-specific** layers into a sub-package keeps
the top-level `layers/` folder reserved for generic building blocks.  
Below is everything you have to touch to make the new layout work.

Directory tree
──────────────
```
layers/
├── __init__.py             # keeps LayerRegistry import helpers
├── base_os.py
├── docker.py
├── networking.py
└── docker_services/
    ├── __init__.py         # registers the three service layers
    ├── grafana.py
    ├── prometheus.py
    └── postgresql.py
```

1. layers/docker_services/\_\_init\_\_.py
-----------------------------------------
```python
"""
Service-specific layers that run on top of Docker Engine
(grafana, prometheus, postgresql, …)
"""
from vmconfig.framework.layers import LayerRegistry

# Explicit imports so the classes are created and we can register them
from .grafana import GrafanaLayer
from .postgresql import PostgresqlLayer
from .prometheus import PrometheusLayer

# Register once at import time
LayerRegistry.register_layer("grafana", GrafanaLayer)
LayerRegistry.register_layer("postgresql", PostgresqlLayer)
LayerRegistry.register_layer("prometheus", PrometheusLayer)

__all__ = [
    "GrafanaLayer",
    "PostgresqlLayer",
    "PrometheusLayer",
]
```

2. layers/\_\_init\_\_.py
-------------------------
Expose everything one level up so old import paths still work:

```python
"""
Public layer API
"""
from vmconfig.framework.layers import LayerRegistry

# Import generic layers
from .base_os import BaseOsLayer        # if you have a class with that name
from .docker import DockerLayer
from .networking import NetworkingLayer

# Import service layers so they self-register
from .docker_services import (
    GrafanaLayer,
    PostgresqlLayer,
    PrometheusLayer,
)

__all__ = [
    "BaseOsLayer",
    "DockerLayer",
    "NetworkingLayer",
    "GrafanaLayer",
    "PostgresqlLayer",
    "PrometheusLayer",
    "LayerRegistry",
]
```

This way both

```python
from layers.grafana import GrafanaLayer
```

and

```python
from layers.docker_services.grafana import GrafanaLayer
```

continue to work.

3. Update template imports (optional)
-------------------------------------
Inside `templates/grafana-postgres/template.py` (or any other template) you
can now drop the explicit imports; all you need is the layer **name** because
`LayerRegistry` already knows it:

```python
class GrafanaPostgresTemplate(ServiceTemplate):
    ...
    vms = {
        "grafana": TemplateVm(
            layers=["base-os", "docker", "grafana", "networking"],
            ...
        ),
        "postgres": TemplateVm(
            layers=["base-os", "docker", "postgresql"],
            ...
        ),
    }
```

4. Packaging / `pyproject.toml`
-------------------------------
If you use a package auto-discovery helper such as

```toml
[tool.setuptools.packages.find]
where = [""]
```

or Poetry’s default, the new sub-package is picked up automatically as long
as it contains an `__init__.py`.  Nothing else to do.

5. Dynamic layer discovery (optional sugar)
-------------------------------------------
If you prefer zero manual `register_layer()` calls you can add this to
`layers/docker_services/__init__.py`:

```python
import pkgutil, importlib, pathlib

_pkg_path = pathlib.Path(__file__).parent

for _mod in pkgutil.iter_modules([str(_pkg_path)]):
    module = importlib.import_module(f"{__name__}.{_mod.name}")
    for attr in dir(module):
        obj = getattr(module, attr)
        if getattr(obj, "name", None) and hasattr(obj, "generate_ansible_tasks"):
            LayerRegistry.register_layer(obj.name, obj)
```

That walks all files below `docker_services/` and registers every class that
looks like a layer.

6. Run it
---------
```bash
vm-config validate --env dev
vm-config apply    --env dev
```

You should see the same task order as before, just sourced from the new
package structure.
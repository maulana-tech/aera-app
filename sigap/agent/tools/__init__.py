"""Importing this package registers every tool.

The registry is populated as a side effect of the @register decorator, so a
tool module that nobody imports is a tool that does not exist. That used to be
spread across api.py and manage.py as a pair of noqa'd import lines, which
meant graph.py on its own had an empty registry: it worked only because api.py
happened to import the tools before it imported graph. Import order is not a
place to keep a guarantee.

One file per agent, named after the agent's code.
"""
from tools import (  # noqa: F401
    compliance,
    demand,
    execution,
    exposure,
    impact,
    inventory,
    logistics,
    precedent,
    procurement,
    simulation,
    sourcing,
    supervisor,
)

# A material or plant argument has to name one on record, whichever model wrote it.
from core import registry as _registry  # noqa: E402
from tools.fetcher import material_id as _material_id  # noqa: E402
from tools.fetcher import plant_id as _plant_id  # noqa: E402

_registry.check_argument("material", _material_id)
for _key in ("plant", "from_plant", "to_plant"):
    _registry.check_argument(_key, _plant_id)

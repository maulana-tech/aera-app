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
    simulation,
    sourcing,
    supervisor,
)

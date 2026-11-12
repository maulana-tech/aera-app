"""Importing this package registers every tool.

The registry is populated by the @register decorator, so a tool module nobody
imports is a tool that does not exist. Each module registers its tools under a
CAPABILITY (agents/roles.py), and agents are granted capabilities.
"""
from tools import (  # noqa: F401
    commerce,
    compliance,
    finance,
    money,
    publishing,
    research,
    skills,
    systems,
    workspace,
)

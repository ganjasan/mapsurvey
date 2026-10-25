"""The tool registry of the MCP server (design D4).

Importing this package registers every tool: each module calls
`registry.register(...)` at import time, so `registry.all_tools()` is the
list once this package has been imported -- in this order, which is the
order `tools/list` presents them in.
"""
from . import account, surveys, sections, questions, imports, responses, share, layers  # noqa: F401, I001 -- registration order
from .registry import all_tools, get, tools_for  # noqa: F401

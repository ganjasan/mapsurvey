"""Tools: what the agent sees in `tools/list` and what runs on `tools/call`.

A `Tool` is a static description, the scope it needs (`None` for `get_me`),
the role the handler will require on the survey (documentation only -- the
check is `api.v1.deps.survey`), a pydantic argument model, and the handler.
Argument models are built from the REST API's input schemas
(`api/v1/schemas.py`) plus the identifying fields, so `extra='forbid'`, field
constraints and the `InputType` enum are the REST ones: the two surfaces accept
the same bodies, and the same editor forms validate them underneath.

`inputSchema` is the model's JSON Schema with `$ref`s inlined -- not every MCP
client resolves `$defs`. Descriptions are string literals here and nowhere
else; nothing in a tool description is ever built from survey content.
"""
import copy
from dataclasses import dataclass
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, create_model

_TOOLS = {}


class Args(BaseModel):
    """Base of every argument model: unknown fields are refused by name."""
    model_config = ConfigDict(extra='forbid')


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    scope: Optional[str]
    role: str
    args: type
    handler: Callable
    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False
    confirm: bool = False

    @property
    def input_schema(self):
        return inline_refs(self.args.model_json_schema())

    @property
    def annotations(self):
        return {
            'title': self.title,
            'readOnlyHint': self.read_only,
            'destructiveHint': self.destructive,
            'idempotentHint': self.idempotent,
            'openWorldHint': False,
        }

    def listing(self):
        return {
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'inputSchema': self.input_schema,
            'annotations': self.annotations,
        }


def args_model(name, base=None, **fields):
    """A pydantic model named `name` with `fields` (`name=(type, Field(...))`)
    on top of `base` (a REST `In` schema) or the bare `Args`."""
    return create_model(name, __base__=base or Args, **fields)


def inline_refs(schema):
    """The schema with every `$ref` replaced by its `$defs` entry (none of the
    REST schemas is recursive; a cycle would be a programming error here)."""
    schema = copy.deepcopy(schema)
    defs = schema.pop('$defs', {})

    def walk(node, depth=0):
        if depth > 32:
            raise ValueError('recursive schema cannot be inlined')
        if isinstance(node, dict):
            if '$ref' in node:
                target = defs[node['$ref'].rsplit('/', 1)[-1]]
                merged = dict(walk(target, depth + 1))
                merged.update({k: walk(v, depth + 1) for k, v in node.items() if k != '$ref'})
                return merged
            return {k: walk(v, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, depth + 1) for v in node]
        return node

    return walk(schema)


def register(tool):
    if tool.name in _TOOLS:
        raise ValueError(f'tool registered twice: {tool.name}')
    _TOOLS[tool.name] = tool
    return tool


def tool(name, *, title, description, scope, role, args, read_only=False, destructive=False,
         idempotent=False, confirm=False):
    """Decorator: `@tool('get_survey', ...)` over the handler."""
    def deco(handler):
        register(Tool(name=name, title=title, description=description, scope=scope, role=role,
                      args=args, handler=handler, read_only=read_only, destructive=destructive,
                      idempotent=idempotent, confirm=confirm))
        return handler
    return deco


def all_tools():
    return list(_TOOLS.values())


def get(name):
    return _TOOLS.get(name)


def tools_for(principal):
    """The tools the token's scopes allow, in registration order."""
    return [t for t in _TOOLS.values() if t.scope is None or principal.has_scope(t.scope)]

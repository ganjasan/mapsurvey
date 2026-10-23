"""Who is acting, and from where -- what a service needs from a request."""
from dataclasses import dataclass
from typing import Optional

SURFACE_EDITOR = 'editor'
SURFACE_API = 'api'
SURFACE_MCP = 'mcp'


@dataclass(frozen=True)
class Actor:
    user: object
    ip: Optional[str] = None
    surface: str = SURFACE_EDITOR

    @classmethod
    def from_request(cls, request, surface=SURFACE_EDITOR):
        from ..abuse import client_ip
        user = request.user if request.user.is_authenticated else None
        return cls(user=user, ip=client_ip(request) or None, surface=surface)

    @property
    def user_id(self):
        return getattr(self.user, 'pk', None)

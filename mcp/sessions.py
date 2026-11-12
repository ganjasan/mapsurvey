"""MCP session ids without server-side state (design D3).

`initialize` answers with an `Mcp-Session-Id` that is a signed value carrying
the token id and a random nonce. The server stores nothing: a later request
may omit the header (a stateless client, or one reconnecting after a
restart), and a present id is checked for its signature and for belonging to
the token that presents it -- an id issued to token A and presented under
token B is a session the server does not know (404, and the client
re-initialises). The nonce keys the per-session tool-call cap.

The payload also carries what analytics needs on every later request and the
stateless server could not otherwise remember (change `mcp-analytics-events`,
D2): the issue time and the client context of `initialize` -- `clientInfo`
name and version and the negotiated protocol version. Ids signed before that
change hold only `t` and `n` and keep verifying, with the context empty.
"""
import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass

from django.core import signing

SALT = 'mcp.session'
CLIENT_NAME_MAX = 64
CLIENT_VERSION_MAX = 32
PROTOCOL_VERSION_MAX = 16


class BadSession(ValueError):
    pass


@dataclass(frozen=True)
class Session:
    nonce: str
    issued_ms: int | None = None
    client_name: str = ''
    client_version: str = ''
    protocol_version: str = ''

    def analytics_id(self):
        """The `$session_id` PostHog groups this session's events by: a UUIDv7
        whose time is the issue time and whose random bits come from the nonce,
        so every request of one session carries the same id (design D3).
        `None` for an id from before the issue time was signed in."""
        if self.issued_ms is None:
            return None
        rand = int.from_bytes(hashlib.sha256(self.nonce.encode()).digest()[:10], 'big')   # 80 bits
        value = (self.issued_ms & ((1 << 48) - 1)) << 80
        value |= 0x7 << 76                                  # version 7
        value |= ((rand >> 68) & 0xFFF) << 64               # rand_a, 12 bits
        value |= 0b10 << 62                                 # RFC 9562 variant
        value |= rand & ((1 << 62) - 1)                     # rand_b, 62 bits
        return str(uuid.UUID(int=value))


def _trim(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def issue(token_id, client=None, protocol_version=None):
    """A signed session id for `token_id`; `client` is the `clientInfo` object of `initialize`."""
    payload = {'t': token_id, 'n': secrets.token_urlsafe(16), 'ts': int(time.time() * 1000)}
    client = client if isinstance(client, dict) else {}
    for key, field, limit in (('c', 'name', CLIENT_NAME_MAX), ('cv', 'version', CLIENT_VERSION_MAX)):
        value = _trim(client.get(field), limit)
        if value:
            payload[key] = value
    version = _trim(protocol_version, PROTOCOL_VERSION_MAX)
    if version:
        payload['pv'] = version
    return signing.dumps(payload, salt=SALT, compress=False)


def verify(value, token_id):
    """The `Session` of `value` when it is ours and belongs to `token_id`; BadSession otherwise."""
    try:
        data = signing.loads(value, salt=SALT)
    except signing.BadSignature:
        raise BadSession('session id does not verify')
    if not isinstance(data, dict) or data.get('t') != token_id or not isinstance(data.get('n'), str):
        raise BadSession('session id belongs to another token')
    issued = data.get('ts')
    return Session(
        nonce=data['n'],
        issued_ms=issued if isinstance(issued, int) and not isinstance(issued, bool) and issued > 0 else None,
        client_name=_trim(data.get('c'), CLIENT_NAME_MAX),
        client_version=_trim(data.get('cv'), CLIENT_VERSION_MAX),
        protocol_version=_trim(data.get('pv'), PROTOCOL_VERSION_MAX),
    )

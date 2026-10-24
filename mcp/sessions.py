"""MCP session ids without server-side state (design D3).

`initialize` answers with an `Mcp-Session-Id` that is a signed value carrying
the token id and a random nonce. The server stores nothing: a later request
may omit the header (a stateless client, or one reconnecting after a
restart), and a present id is checked for its signature and for belonging to
the token that presents it -- an id issued to token A and presented under
token B is a session the server does not know (404, and the client
re-initialises). The nonce keys the per-session tool-call cap.
"""
import secrets

from django.core import signing

SALT = 'mcp.session'


class BadSession(ValueError):
    pass


def issue(token_id):
    return signing.dumps({'t': token_id, 'n': secrets.token_urlsafe(16)}, salt=SALT, compress=False)


def verify(value, token_id):
    """The nonce of `value` when it is ours and belongs to `token_id`; BadSession otherwise."""
    try:
        data = signing.loads(value, salt=SALT)
    except signing.BadSignature:
        raise BadSession('session id does not verify')
    if not isinstance(data, dict) or data.get('t') != token_id or not isinstance(data.get('n'), str):
        raise BadSession('session id belongs to another token')
    return data['n']

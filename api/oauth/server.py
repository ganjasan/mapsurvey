"""oauthlib's pre-configured `Server` minus the grants this platform does not
issue (change oauth-server, D1).

The metadata document says `authorization_code` and `refresh_token`; the
server must agree, or a confidential client could still talk oauthlib into a
`client_credentials` or device-code token nobody advertised. Removing the
handlers makes the endpoint answer `unsupported_grant_type`, which is the
RFC 6749 §5.2 answer, instead of the `unauthorized_client` a validator veto
would produce.
"""
from oauthlib.oauth2 import Server as OAuthlibServer

GRANT_TYPES = ('authorization_code', 'refresh_token')
RESPONSE_TYPES = ('code',)


class Server(OAuthlibServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for grant in list(self._grant_types):
            if grant not in GRANT_TYPES:
                del self._grant_types[grant]
        for response_type in list(self._response_types):
            if response_type not in RESPONSE_TYPES:
                del self._response_types[response_type]

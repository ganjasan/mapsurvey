"""The consent form (change oauth-server, D6).

The toolkit's `AllowForm` carries the requested scopes in a hidden `scope`
field and issues exactly that. Ours issues less: `surveys:publish` and
`surveys:delete` -- the calls that cannot be undone -- are switches, off by
default, and the issued scope is the requested non-dangerous scopes plus the
switches the creator ticked. The requested set rides a SIGNED hidden field
so that an edited `scope` field cannot add a scope the client never asked for.
"""
from django import forms
from django.core import signing
from oauth2_provider.forms import AllowForm

from .. import scopes as scope_registry

SIGNING_SALT = 'api.oauth.consent'


def switch_name(scope):
    return 'switch_' + scope.replace(':', '_')


class ConsentForm(AllowForm):
    requested = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for scope in scope_registry.SWITCH_SCOPES:
            self.fields[switch_name(scope)] = forms.BooleanField(required=False)

    @staticmethod
    def sign_requested(scopes):
        return signing.dumps(list(scopes), salt=SIGNING_SALT)

    def requested_scopes(self):
        try:
            return list(signing.loads(self.cleaned_data.get('requested') or '', salt=SIGNING_SALT))
        except signing.BadSignature:
            return []

    def clean(self):
        cleaned = super().clean()
        requested = self.requested_scopes()
        granted = [s for s in requested if s not in scope_registry.SWITCH_SCOPES]
        granted += [s for s in requested
                    if s in scope_registry.SWITCH_SCOPES and cleaned.get(switch_name(s))]
        cleaned['scope'] = scope_registry.to_string(granted)
        return cleaned

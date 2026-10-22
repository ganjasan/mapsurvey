from django import forms
from django.utils.translation import gettext_lazy as _

from survey.models import Membership

from . import scopes as scope_registry
from . import tokens
from .models import AUDIENCE_API, AUDIENCE_MCP

ALL_WORKSPACES = ''


class PersonalTokenForm(forms.Form):
    label = forms.CharField(max_length=80, label=_('Name'),
                            help_text=_('What this token is for, e.g. "QGIS plug-in" or "Claude Code".'))
    scopes = forms.MultipleChoiceField(
        choices=[(k, scope_registry.LABELS[k]) for k in scope_registry.SCOPES],
        widget=forms.CheckboxSelectMultiple, initial=list(scope_registry.DEFAULT_SCOPES),
        label=_('Permissions'),
    )
    audiences = forms.MultipleChoiceField(
        choices=[(AUDIENCE_API, _('REST API')), (AUDIENCE_MCP, _('MCP server'))],
        widget=forms.CheckboxSelectMultiple, initial=[AUDIENCE_API, AUDIENCE_MCP],
        label=_('Use with'),
    )
    organization = forms.ChoiceField(required=False, label=_('Workspace'))
    expiry = forms.ChoiceField(
        choices=[
            (tokens.EXPIRY_90_DAYS, _('90 days')),
            (tokens.EXPIRY_1_YEAR, _('1 year')),
            (tokens.EXPIRY_NEVER, _('Never')),
        ],
        initial=tokens.EXPIRY_NEVER, label=_('Expires'),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.memberships = list(
            Membership.objects.filter(user=user).select_related('organization').order_by('organization__name')
        )
        self.fields['organization'].choices = [(ALL_WORKSPACES, _('All my workspaces'))] + [
            (str(m.organization.pk), m.organization.name) for m in self.memberships
        ]

    def clean_organization(self):
        value = self.cleaned_data.get('organization') or ALL_WORKSPACES
        if value == ALL_WORKSPACES:
            return None
        for m in self.memberships:
            if str(m.organization.pk) == value:
                return m.organization
        raise forms.ValidationError(_('Choose one of your workspaces.'))

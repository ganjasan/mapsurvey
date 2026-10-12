from django import forms
from django.utils.translation import gettext_lazy as _

from survey.models import SurveyHeader

from .models import CANCELLATION_REASONS, ProHelpRequest


class ProHelpRequestForm(forms.ModelForm):
    class Meta:
        model = ProHelpRequest
        fields = ('kind', 'survey', 'message', 'contact_email')
        labels = {
            'kind': _('What do you need'),
            'survey': _('About which survey (optional)'),
            'message': _('Tell us about the project'),
            'contact_email': _('Where should we reply'),
        }
        widgets = {
            'kind': forms.Select(attrs={'class': 'form-control'}),
            'survey': forms.Select(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 7, 'maxlength': 5000,
                                             'placeholder': _('What is the project, who is it for, and what would help most right now?')}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        # Only this organisation's surveys are offerable; a survey id from
        # another organisation fails validation rather than leaking a title.
        self.fields['survey'].queryset = (
            SurveyHeader.objects.filter(organization=organization, deleted_at__isnull=True, canonical_survey__isnull=True)
            .order_by('-updated_at')
        )
        self.fields['survey'].required = False
        self.fields['survey'].empty_label = _('— not about one survey —')


class CancelForm(forms.Form):
    reason = forms.TypedChoiceField(
        choices=[(k, v) for k, v in CANCELLATION_REASONS if k != 7], coerce=int,
        label=_('Why are you cancelling?'), widget=forms.RadioSelect,
    )
    note = forms.CharField(required=False, max_length=500, label=_('Anything we should know?'),
                           widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}))

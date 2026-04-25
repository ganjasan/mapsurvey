from django import forms
from .models import SurveyHeader, SurveySection, Question, Organization, BASEMAP_CHOICES


class SurveyHeaderForm(forms.ModelForm):
    class Meta:
        model = SurveyHeader
        fields = ['name', 'redirect_url', 'available_languages', 'visibility', 'thanks_html', 'cover_image', 'basemaps', 'default_basemap']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'survey_name'}),
            'redirect_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#'}),
            'available_languages': forms.HiddenInput(attrs={'id': 'id_available_languages'}),
            'visibility': forms.Select(attrs={'class': 'form-control'}),
            'thanks_html': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '{"en": "<h1>Thanks!</h1>"}'}),
            'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'basemaps': forms.HiddenInput(attrs={'id': 'id_basemaps'}),
            'default_basemap': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Drop the implicit blank option from the dropdown so the editor
        # never offers "no default" as a choice. A missing or invalid value
        # is still tolerated server-side and auto-fixed in ``clean()``,
        # which keeps existing rows (and tests posting without the field)
        # working without an additional migration.
        self.fields['default_basemap'].required = False
        self.fields['default_basemap'].empty_label = None
        self.fields['default_basemap'].choices = list(BASEMAP_CHOICES)

    def clean_basemaps(self):
        VALID = {slug for slug, _ in BASEMAP_CHOICES}
        value = self.cleaned_data.get('basemaps') or []
        if not isinstance(value, list):
            raise forms.ValidationError("Invalid basemaps value.")
        cleaned = [slug for slug in value if slug in VALID]
        # ``basemaps`` itself can never be empty either — fall back to streets.
        return cleaned or ['streets']

    def clean(self):
        cleaned = super().clean()
        basemaps = cleaned.get('basemaps') or ['streets']
        default = cleaned.get('default_basemap')
        if not default or default not in basemaps:
            # Auto-pick the first enabled basemap so a survey never ends up
            # with an unselectable / orphan default.
            cleaned['default_basemap'] = basemaps[0]
        return cleaned


class SurveySectionForm(forms.ModelForm):
    class Meta:
        model = SurveySection
        fields = ['title', 'subheading', 'code']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subheading': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 8}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['name', 'subtext', 'input_type', 'required', 'color', 'icon_class', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subtext': forms.TextInput(attrs={'class': 'form-control'}),
            'input_type': forms.Select(attrs={'class': 'form-control'}),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'icon_class': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fas fa-map-marker-alt'}),
        }
        help_texts = {
            'icon_class': '<a href="https://fontawesome.com/v5/search" target="_blank" rel="noopener">Font Awesome</a> class',
        }

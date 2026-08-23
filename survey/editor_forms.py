from django import forms
from .models import SurveyHeader, SurveySection, Question, Organization, BASEMAP_CHOICES
from .html_sanitize import coerce_creator_html

SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon')

USE_CASE_CHOICES = (
    ('urban_planning', 'Urban planning'),
    ('citizen_science', 'Citizen science'),
    ('school_routes', 'School routes'),
    ('event_mapping', 'Event mapping'),
    ('other', 'Other'),
)


class SurveyCreateForm(forms.ModelForm):
    """Minimal creation form — name, languages, and (via the view) map area.

    The rest (redirect URL, visibility, thanks page, cover image, basemaps)
    gets model defaults and is edited later in the Survey settings panel, which
    uses the full ``SurveyHeaderForm``. Languages are asked up front because
    they shape every later step (question text, translations).
    """
    class Meta:
        model = SurveyHeader
        fields = ['name', 'available_languages']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Park improvements'}),
            'available_languages': forms.HiddenInput(attrs={'id': 'id_available_languages'}),
        }


class SurveyBriefForm(forms.Form):
    """The AI brief — what the creator tells the model about their project.

    Not a ModelForm: none of these fields belong on ``SurveyHeader``. They are
    authoring metadata that stops meaning anything the moment a human edits
    the generated draft, so they live only on the generation event.

    Only ``goal`` is required. The other three sharpen the draft but a creator
    who types one sentence and hits Generate should still get a survey — the
    point of the feature is removing work, not relocating it.
    """

    # Server-side only: the brief shares one <form> with the "Create empty"
    # submit, and the browser validates the whole form on any submit. With
    # HTML5 `required` on `goal`, clicking "Create empty" with an untouched
    # brief was refused by the browser -- the POST never left the page, and the
    # creator got a "fill this in" tooltip pointing at the AI panel they were
    # declining to use. `goal` is still required for the generate path, where
    # `_start_survey_generation` validates it and renders the errors into the
    # status slot.
    use_required_attribute = False

    goal = forms.CharField(
        label='What do you want to find out?',
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'e.g. Where traffic congestion is worst in Treviglio and why',
        }),
    )
    audience = forms.CharField(
        required=False,
        label='Who will answer?',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'e.g. Residents of Treviglio, all ages',
        }),
    )
    map_target = forms.CharField(
        required=False,
        label='What should they mark on the map?',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'e.g. Congestion spots, dangerous crossings',
        }),
    )
    use_case = forms.ChoiceField(
        required=False, choices=USE_CASE_CHOICES, initial='urban_planning',
        widget=forms.RadioSelect(),
    )

    def clean_use_case(self):
        return self.cleaned_data.get('use_case') or 'other'


class SurveyHeaderForm(forms.ModelForm):
    default_rating_display_style = forms.ChoiceField(
        choices=(('scale_strip', 'Compact scale'), ('list_pips', 'Labeled list'),
                 ('stars', 'Stars')),
        required=False,
        widget=forms.RadioSelect(),
        label='Rating questions',
    )

    class Meta:
        model = SurveyHeader
        # thanks_html now has its own WYSIWYG editor panel; show_branding is a
        # future paid-tier flag on the model, not a creator-facing field.
        fields = ['name', 'redirect_url', 'available_languages', 'visibility', 'cover_image', 'basemaps', 'default_basemap']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'survey_name'}),
            'redirect_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#'}),
            'available_languages': forms.HiddenInput(attrs={'id': 'id_available_languages'}),
            'visibility': forms.Select(attrs={'class': 'form-control'}),
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
        if self.instance and self.instance.pk:
            self.fields['default_rating_display_style'].initial = self.instance.get_default_rating_display_style()
        else:
            self.fields['default_rating_display_style'].initial = 'scale_strip'

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

    def save(self, commit=True):
        obj = super().save(commit=False)
        style = self.cleaned_data.get('default_rating_display_style') or 'scale_strip'
        settings = dict(obj.style_settings or {})
        settings['rating_display_style'] = style
        obj.style_settings = settings
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class SurveySectionForm(forms.ModelForm):
    class Meta:
        model = SurveySection
        fields = ['title', 'subheading', 'code']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subheading': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 8}),
        }

    def clean_subheading(self):
        # Rendered |safe on the section page — and was already, before it had an
        # editor, which is the hole this closes.
        return coerce_creator_html(self.cleaned_data.get('subheading'))


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['name', 'subtext', 'input_type', 'required', 'color', 'icon_class', 'image', 'display_style']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subtext': forms.TextInput(attrs={'class': 'form-control'}),
            'input_type': forms.Select(attrs={'class': 'form-control'}),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'icon_class': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fas fa-map-marker-alt'}),
            'display_style': forms.RadioSelect(),
        }
        help_texts = {
            'icon_class': '<a href="https://fontawesome.com/v5/search" target="_blank" rel="noopener">Font Awesome</a> class',
        }

    def __init__(self, *args, is_subquestion=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['display_style'].required = False
        # A new question starts on a concrete type instead of the "---------"
        # empty option, so the picker cards and the live preview have a
        # selection to agree on from the first render.
        if not self.instance.pk:
            self.initial.setdefault('input_type', 'text')
        if is_subquestion:
            field = self.fields['input_type']
            field.choices = [
                (value, label) for value, label in field.choices
                if value not in SUBQUESTION_DISALLOWED_INPUT_TYPES
            ]

    def clean_display_style(self):
        return self.cleaned_data.get('display_style') or 'default'

    def clean(self):
        cleaned = super().clean()
        # Subtext is rich text for every type now — the block body for `html`,
        # a formatted helper line for the rest — and all of it renders |safe to
        # respondents. This is the one place all three question-saving views
        # pass through, so the allow-list belongs here.
        cleaned['subtext'] = coerce_creator_html(cleaned.get('subtext'))
        style = cleaned.get('display_style') or 'default'
        input_type = cleaned.get('input_type')
        if input_type == 'choice':
            if style not in ('default', 'dropdown'):
                cleaned['display_style'] = 'default'
        elif style == 'dropdown':
            cleaned['display_style'] = 'default'
        return cleaned

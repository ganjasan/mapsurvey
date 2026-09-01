from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from .models import SurveyHeader, SurveySection, Question, Organization, BASEMAP_CHOICES
from .html_sanitize import coerce_creator_html
from .layers import layers_for
from .question_types import GEO_TYPES

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
        labels = {
            'name': _('Survey name'),
            'available_languages': _('Available languages'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Park improvements')}),
            'available_languages': forms.HiddenInput(attrs={'id': 'id_available_languages'}),
        }


class SurveyRenameForm(forms.ModelForm):
    """The name, alone — what the editor header's inline rename writes.

    Deliberately not ``SurveyHeaderForm``: that form binds languages, basemaps
    and default_basemap too, so a POST carrying only ``name`` would bind those
    as absent and could rewrite them. A one-field ModelForm cannot damage
    anything else, and still runs the model's own ``max_length`` and
    ``validate_url_name`` so the header and Survey settings can never disagree
    on what a valid name is.
    """
    class Meta:
        model = SurveyHeader
        fields = ['name']
        labels = {'name': _('Survey name')}


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
        label=_('What do you want to find out?'),
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': _('e.g. Where traffic congestion is worst in Treviglio and why'),
        }),
    )
    audience = forms.CharField(
        required=False,
        label=_('Who will answer?'),
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': _('e.g. Residents of Treviglio, all ages'),
        }),
    )
    map_target = forms.CharField(
        required=False,
        label=_('What should they mark on the map?'),
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': _('e.g. Congestion spots, dangerous crossings'),
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
        label=_('Rating questions'),
    )
    # Theming lives in style_settings, not on the model. The checkbox exists
    # because <input type=color> cannot be empty — unchecked means "no custom
    # accent", whatever the color input happens to hold.
    use_accent_color = forms.BooleanField(
        required=False, label=_('Custom accent color'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_use_accent_color'}),
    )
    accent_color = forms.CharField(
        required=False, label=_('Accent color'),
        validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Use a hex color like #7a1f2b.')],
        widget=forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'id': 'id_accent_color'}),
    )

    class Meta:
        model = SurveyHeader
        # thanks_html now has its own WYSIWYG editor panel; show_branding is a
        # future paid-tier flag on the model, not a creator-facing field.
        fields = ['name', 'redirect_url', 'available_languages', 'visibility', 'cover_image', 'basemaps', 'default_basemap']
        labels = {
            # "Name" with the placeholder "survey_name" read as an identifier
            # nobody should touch, which is how surveys ended up called things
            # like demo_city_feedback. It is the title respondents see.
            'name': _('Survey name'),
            'redirect_url': _('Redirect URL'),
            'available_languages': _('Available languages'),
            'visibility': _('Visibility'),
            'cover_image': _('Cover image'),
            'basemaps': _('Base maps'),
            'default_basemap': _('Default base map'),
        }
        widgets = {
            # Django renders maxlength from the model field; data-char-counter
            # makes that limit visible before it bites (editor_survey_rename.js),
            # on both the settings page and its HTMX panel twin.
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': _('e.g. Park improvements'),
                'data-char-counter': '',
            }),
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
            accent = self.instance.get_accent_color()
            self.fields['use_accent_color'].initial = bool(accent)
            self.fields['accent_color'].initial = accent or '#2f5cff'
        else:
            self.fields['default_rating_display_style'].initial = 'scale_strip'
            self.fields['accent_color'].initial = '#2f5cff'

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
        accent = self.cleaned_data.get('accent_color')
        if self.cleaned_data.get('use_accent_color') and accent:
            settings['accent_color'] = accent
        else:
            settings.pop('accent_color', None)
        obj.style_settings = settings
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class SurveySectionForm(forms.ModelForm):
    class Meta:
        model = SurveySection
        fields = ['title', 'subheading', 'code', 'layout', 'next_label']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subheading': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 8}),
            'layout': forms.Select(attrs={'class': 'form-control', 'id': 'id_section_layout'}),
            'next_label': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 30, 'placeholder': _('Next')}),
        }
        # ONE labels dict. There were two assignments here; the second silently
        # replaced the first, so only the fields it named had labels and the
        # rest fell back to Django's field-name derivation — reaching the
        # creator in English whatever their interface language.
        #
        # Set here rather than as model verbose_name: a verbose_name change
        # generates a migration for no schema benefit.
        labels = {
            'title': _('Title'),
            'subheading': _('Subheading'),
            'code': _('Code'),
            'layout': _('Layout'),
            'next_label': _('Button label'),
        }
        help_texts = {
            'layout': _('Map: questions beside the map. Form: a classic full-width form — no map, so geo questions are unavailable.'),
            'next_label': _('Label of this section\'s forward button, e.g. "Start" on a welcome section. Empty = Next / Finish.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A POST without the field (older open forms, tests) keeps the stored
        # layout instead of failing validation or silently flipping to map.
        self.fields['layout'].required = False

    def clean_subheading(self):
        # Rendered |safe on the section page — and was already, before it had an
        # editor, which is the hole this closes.
        return coerce_creator_html(self.cleaned_data.get('subheading'))

    def clean_layout(self):
        layout = self.cleaned_data.get('layout')
        if not layout:
            layout = self.instance.layout if self.instance.pk else 'map'
        if layout == 'form' and self.instance.pk:
            geo_questions = Question.objects.filter(
                survey_section=self.instance, input_type__in=GEO_TYPES,
            ).order_by('order_number')
            if geo_questions.exists():
                names = ', '.join(
                    (q.name or q.code) for q in geo_questions
                )
                raise forms.ValidationError(
                    f'A form section cannot hold map questions. '
                    f'Move or delete first: {names}.'
                )
        return layout

    def save(self, commit=True):
        """Fold the reference-layer checklist into the model.

        The checklist stores what is *hidden*, so a layer added later shows up
        everywhere without touching any section. Only IDs belonging to this
        survey survive — a stale or forged one would otherwise sit in the JSON
        forever.
        """
        section = super().save(commit=False)
        if self.data and 'reference_layers_submitted' in self.data:
            survey = section.survey_header or (self.instance.survey_header if self.instance.pk else None)
            if survey is not None:
                valid_ids = set(layers_for(survey).values_list('id', flat=True))
                shown = set()
                for raw in self.data.getlist('visible_layers'):
                    try:
                        shown.add(int(raw))
                    except (TypeError, ValueError):
                        continue
                section.hidden_layers = sorted(valid_ids - shown)
        if commit:
            section.save()
        return section


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['name', 'subtext', 'input_type', 'required', 'color', 'icon_class', 'image', 'display_style']
        labels = {
            'name': _('Name'),
            'subtext': _('Subtext'),
            'input_type': _('Input type'),
            'required': _('Required'),
            'color': _('Color'),
            'icon_class': _('Icon class'),
            'image': _('Image'),
            'display_style': _('Display style'),
        }
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

    def __init__(self, *args, is_subquestion=False, section=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['display_style'].required = False
        # A new question starts on a concrete type instead of the "---------"
        # empty option, so the picker cards and the live preview have a
        # selection to agree on from the first render.
        if not self.instance.pk:
            self.initial.setdefault('input_type', 'text')
        if section is not None and section.layout == 'form':
            # A form section has no map — filtering the field's choices both
            # removes the geo group from the type picker (picker_groups_for
            # builds groups from these choices) and rejects a geo input_type
            # server-side as an invalid choice.
            field = self.fields['input_type']
            field.choices = [
                (value, label) for value, label in field.choices
                if value not in GEO_TYPES
            ]
        if is_subquestion:
            field = self.fields['input_type']
            field.choices = [
                (value, label) for value, label in field.choices
                if value not in SUBQUESTION_DISALLOWED_INPUT_TYPES
            ]
        from django.conf import settings as conf_settings
        if not getattr(conf_settings, 'FILE_UPLOAD_QUESTIONS', False):
            # Kill switch: filtering the choices both drops the Files group
            # from the picker (picker_groups_for builds from these choices)
            # and rejects the types server-side as invalid — same double duty
            # as the form-layout geo filter above.
            from survey.models import FILE_INPUT_TYPES
            field = self.fields['input_type']
            field.choices = [
                (value, label) for value, label in field.choices
                if value not in FILE_INPUT_TYPES
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


class OrganizationSettingsForm(forms.ModelForm):
    """Name + slug for the organization settings page.

    A ModelForm, not hand-read POST values, because the whole defect this
    replaces was that `SlugField`'s validator never ran: Django applies field
    validators from `full_clean()`, and the previous view checked only
    uniqueness before assigning `org.slug` directly. The field looked validated
    in the model and accepted "CBPR Summer 26' PM" at runtime, which reverses to
    nothing and 500s every page that renders the account dropdown.
    """

    class Meta:
        model = Organization
        fields = ('name', 'slug')
        labels = {
            'name': 'Name',
            'slug': 'Slug',
        }
        help_texts = {
            'slug': 'URL identifier — letters, numbers, hyphens and underscores only.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['slug'].required = True
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')
        # Client-side echo of the server rule, so the common mistake (typing a
        # display name into the slug box) is caught before the round trip.
        self.fields['slug'].widget.attrs.setdefault('pattern', r'[-\w.]+')

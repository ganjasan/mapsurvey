from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from survey import marker_icons
from .models import SurveyHeader, SurveySection, Question, QuestionGroup, Organization, BASEMAP_CHOICES, MAPLESS_LAYOUTS
from .html_sanitize import coerce_creator_html
from .redirects import NO_REDIRECT, clean_redirect_url, is_valid_redirect, tidy_redirect_input
from .layers import layers_for
from .question_types import GEO_TYPES, MAP_ONLY_TYPES, SHARED_MAP_SOURCE_TYPES, allowed_display_styles

# Parent-capable types cannot themselves be sub-questions: a sub-question lives
# inside an object's popup, and an object cannot contain more objects.
SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon', 'spraycan', 'layer_objects')

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
    # "Redirect URL" as a bare text box pre-filled with "#" collected hashtags,
    # thank-you messages and "#https://..." -- and every one of them left
    # respondents pressing Finish on the last page (#271). The creator now picks
    # what happens; the address box is only for the second option.
    finish_action = forms.ChoiceField(
        choices=(('thanks', _('Show the thank-you page')),
                 ('link', _('Open a web address'))),
        required=False,
        widget=forms.RadioSelect(),
        label=_('After the last page'),
    )
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
        # thanks_html now has its own WYSIWYG editor panel. show_branding is the
        # Pro switch for the "Made with Mapsurvey" badge: editable only when the
        # organisation holds the `unbranded` entitlement (see __init__), inert
        # -- disabled in the form, ignored on POST -- for everyone else.
        fields = ['name', 'redirect_url', 'available_languages', 'visibility', 'cover_image', 'basemaps',
                  'default_basemap', 'show_branding']
        labels = {
            # "Name" with the placeholder "survey_name" read as an identifier
            # nobody should touch, which is how surveys ended up called things
            # like demo_city_feedback. It is the title respondents see.
            'name': _('Survey name'),
            'redirect_url': _('Web address'),
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
            'redirect_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'available_languages': forms.HiddenInput(attrs={'id': 'id_available_languages'}),
            'visibility': forms.Select(attrs={'class': 'form-control'}),
            'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'basemaps': forms.HiddenInput(attrs={'id': 'id_basemaps'}),
            'default_basemap': forms.Select(attrs={'class': 'form-control'}),
            'show_branding': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_show_branding'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A disabled field keeps its initial value whatever the POST says, which
        # is exactly the "submitted values are ignored" rule for Free organisations.
        # "May": the plan includes `unbranded` or a live Pro trial has a switch-off
        # left (change pro-trial-allowances); `consumes_unbranded()` tells the
        # service when a save spends one.
        from billing.entitlements import for_organization
        org = self.instance.organization if self.instance and self.instance.pk else None
        ent = for_organization(org) if org is not None else None
        self.unbranded = ent is not None and ent.may('unbranded')
        self.unbranded_by_plan = ent is not None and ent.has('unbranded')
        self._branding_before = bool(self.instance.show_branding) if self.instance and self.instance.pk else True
        self.fields['show_branding'].required = False
        self.fields['show_branding'].label = _('Show the "Made with Mapsurvey" badge')
        # Disabled = the POST is ignored. Left enabled on a survey whose badge is
        # already off (switched off under a trial or a lapsed plan), so the
        # creator can always turn the badge back on; `clean_show_branding`
        # refuses a new switch-off there.
        if not self.unbranded and self._branding_before:
            self.fields['show_branding'].disabled = True
        # Drop the implicit blank option from the dropdown so the editor
        # never offers "no default" as a choice. A missing or invalid value
        # is still tolerated server-side and auto-fixed in ``clean()``,
        # which keeps existing rows (and tests posting without the field)
        # working without an additional migration.
        self.fields['default_basemap'].required = False
        self.fields['default_basemap'].empty_label = None
        self.fields['default_basemap'].choices = list(BASEMAP_CHOICES)
        # "#" is how this model spells "no redirect" (views.py sends the
        # respondent to the thanks page when it sees it), and the model gives
        # the field that default -- but the field is not blank=True, so the
        # ModelForm made it required. A creator who cleared the box because
        # they want no redirect got "This field is required" back on EVERY
        # autosave of the whole panel, which is the permanent "Not saved --
        # retry" Replay Vision caught on 2026-09-21 (backlog #187).
        self.fields['redirect_url'].required = False
        self.fields['redirect_url'].help_text = _(
            'Respondents are sent here after the last page, for example '
            'https://www.facebook.com/yourproject')
        # Never show the stored "#" in the box: creators typed their URL after
        # it. A stored value that is not a working link reads as "thank-you
        # page" -- that is where respondents go with it anyway.
        stored = clean_redirect_url(self.instance.redirect_url if self.instance else '')
        self.fields['finish_action'].initial = 'thanks' if stored == NO_REDIRECT else 'link'
        self.initial['redirect_url'] = '' if stored == NO_REDIRECT else stored
        if self.instance and self.instance.pk:
            self.fields['default_rating_display_style'].initial = self.instance.get_default_rating_display_style()
            accent = self.instance.get_accent_color()
            self.fields['use_accent_color'].initial = bool(accent)
            self.fields['accent_color'].initial = accent or '#2f5cff'
        else:
            self.fields['default_rating_display_style'].initial = 'scale_strip'
            self.fields['accent_color'].initial = '#2f5cff'

    def clean_show_branding(self):
        value = self.cleaned_data.get('show_branding')
        # The field is enabled without the entitlement only to let the badge be
        # turned back ON; a switch-off there keeps the stored value.
        if not self.unbranded and self._branding_before and not value:
            return True
        return value

    def consumes_unbranded(self):
        """This save switches the badge off on a workspace whose PLAN lacks
        `unbranded`: it spends one Pro-trial switch-off. Call after is_valid()."""
        return (not self.unbranded_by_plan and self._branding_before
                and self.cleaned_data.get('show_branding') is False)

    def clean_redirect_url(self):
        # Empty means "no redirect", which this model stores as "#".
        raw = (self.cleaned_data.get('redirect_url') or '').strip()
        action = self.data.get(self.add_prefix('finish_action'))
        if action == 'thanks' or raw in ('', NO_REDIRECT):
            return NO_REDIRECT
        # Fix what a person would fix by hand ("#https://...", "www....",
        # "Https://"), then insist on a real address. Refusing beats silently
        # storing "#": the creator would believe the link works.
        value = tidy_redirect_input(raw)
        if not is_valid_redirect(value):
            raise forms.ValidationError(_(
                'Enter a full web address, for example '
                'https://www.facebook.com/yourproject'))
        return value

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
        # The layout controls follow `layout` so the modal renders them as one
        # block (change section-layout-controls).
        fields = ['title', 'subheading', 'code', 'layout', 'panel_side', 'panel_width', 'content_width',
                  'content_valign', 'stage_image',
                  'next_label']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subheading': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 8}),
            'layout': forms.Select(attrs={'class': 'form-control', 'id': 'id_section_layout'}),
            'panel_side': forms.Select(attrs={'class': 'form-control'}),
            'panel_width': forms.Select(attrs={'class': 'form-control'}),
            'content_width': forms.Select(attrs={'class': 'form-control'}),
            'content_valign': forms.Select(attrs={'class': 'form-control'}),
            'stage_image': forms.ClearableFileInput(attrs={'class': 'form-control-file', 'accept': 'image/*'}),
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
            'panel_side': _('Panel side'),
            'panel_width': _('Panel width'),
            'content_width': _('Content width'),
            'content_valign': _('Content vertical position'),
            'stage_image': _('Picture'),
            'next_label': _('Button label'),
        }
        help_texts = {
            'layout': _('Map: questions beside the map. Picture: questions beside a picture, e.g. a welcome page. Form: a classic full-width form. Picture and Form have no map, so geo questions are unavailable.'),
            'panel_side': _('Where the questions sit on a computer screen. On a phone they always cover the map.'),
            'panel_width': _('How much of a computer screen the questions take.'),
            'content_width': _('Centred column: the text and questions keep a comfortable reading width in the middle of a wide panel.'),
            'content_valign': _('Middle: a short page sits in the middle of the panel instead of at its top.'),
            'stage_image': _('Shown beside the questions. Empty = the survey cover image.'),
            'next_label': _('Label of this section\'s forward button, e.g. "Start" on a welcome section. Empty = Next / Finish.'),
        }

    def __init__(self, *args, lock_structure=False, **kwargs):
        super().__init__(*args, **kwargs)
        # A POST without the field (older open forms, tests) keeps the stored
        # layout instead of failing validation or silently flipping to map.
        self.fields['layout'].required = False
        # Same for the layout controls: a POST without them (autosave of an
        # older open modal, the API's partial bind) keeps what is stored.
        for name in ('panel_side', 'panel_width', 'content_width', 'content_valign'):
            self.fields[name].required = False
        # On a live survey the code is structure (rules and comments point at
        # it): rendered disabled, and a posted value is ignored.
        if lock_structure:
            self.fields['code'].disabled = True

    def clean_subheading(self):
        # Rendered |safe on the section page — and was already, before it had an
        # editor, which is the hole this closes.
        return coerce_creator_html(self.cleaned_data.get('subheading'))

    def clean_panel_side(self):
        return self.cleaned_data.get('panel_side') or self.instance.panel_side or 'left'

    def clean_panel_width(self):
        return self.cleaned_data.get('panel_width') or self.instance.panel_width or 'default'

    def clean_content_width(self):
        return self.cleaned_data.get('content_width') or self.instance.content_width or 'full'

    def clean_content_valign(self):
        return self.cleaned_data.get('content_valign') or self.instance.content_valign or 'top'

    def clean_layout(self):
        layout = self.cleaned_data.get('layout')
        if not layout:
            layout = self.instance.layout if self.instance.pk else 'map'
        if layout in MAPLESS_LAYOUTS and self.instance.pk:
            geo_questions = Question.objects.filter(
                survey_section=self.instance, input_type__in=GEO_TYPES,
            ).order_by('order_number')
            if geo_questions.exists():
                names = ', '.join(
                    (q.name or q.code) for q in geo_questions
                )
                raise forms.ValidationError(
                    f'A section without a map (Form or Picture) cannot hold map questions. '
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
        if commit:
            section.save()
        return section


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['name', 'subtext', 'input_type', 'required', 'color', 'icon_class', 'spray_brush', 'tap_to_place', 'image', 'display_style',
                  'layer', 'min_objects', 'objects_search', 'panel_mode', 'share_with_respondents']
        labels = {
            'name': _('Name'),
            'subtext': _('Subtext'),
            'input_type': _('Input type'),
            'required': _('Required'),
            'color': _('Color'),
            'icon_class': _('Icon class'),
            'spray_brush': _('Brush size'),
            'tap_to_place': _('A tap on the map places a mark'),
            'image': _('Image'),
            'display_style': _('Display style'),
            'layer': _('Layer'),
            'min_objects': _('Minimum objects'),
            'objects_search': _('Search and category chips'),
            'panel_mode': _('In the panel'),
            'share_with_respondents': _('Visible to other respondents'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subtext': forms.TextInput(attrs={'class': 'form-control'}),
            'input_type': forms.Select(attrs={'class': 'form-control'}),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'icon_class': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fas fa-map-marker-alt'}),
            'spray_brush': forms.Select(attrs={'class': 'form-control'}),
            'tap_to_place': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_style': forms.RadioSelect(),
            'layer': forms.Select(attrs={'class': 'form-control'}),
            'min_objects': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'objects_search': forms.Select(attrs={'class': 'form-control'}),
            'panel_mode': forms.RadioSelect,
        }
        help_texts = {
            'tap_to_place': _('Works only while this is the only map question on its page.'),
            'icon_class': _('Pick from the catalog, or type a <a href="https://fontawesome.com/v5/search" target="_blank" rel="noopener">Font Awesome</a> class or a map icon name such as <code>maki:bus</code>.'),
        }

    def __init__(self, *args, is_subquestion=False, section=None, lock_structure=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['display_style'].required = False
        # On a live survey the type and the bound layer are structure: the
        # stored value wins whatever is posted (change edit-live-survey).
        self.lock_structure = lock_structure
        # Only a spraycan question carries a brush; every other POST omits it.
        self.fields['spray_brush'].required = False
        # A new question starts on a concrete type instead of the "---------"
        # empty option, so the picker cards and the live preview have a
        # selection to agree on from the first render.
        if not self.instance.pk:
            self.initial.setdefault('input_type', 'text')
        # Objects on the map: the layer picker lists the survey's layers
        # (resolved to the canonical owner, so a draft copy sees them too);
        # without any layer — or with the layers kill switch off — the type is
        # not offered at all, which also rejects it server-side.
        from django.conf import settings as conf_settings
        from .layers import layers_for
        survey = section.survey_header if section is not None else (
            self.instance.survey_section.survey_header if self.instance.pk else None)
        # The section the question lives in, for the one-layer-per-section rule.
        self.section = section if section is not None else (
            self.instance.survey_section if self.instance.pk else None)
        layer_qs = layers_for(survey) if (survey is not None and conf_settings.MAP_REFERENCE_LAYERS) else None
        self.fields['layer'].required = False
        self.fields['layer'].queryset = layer_qs if layer_qs is not None else self.fields['layer'].queryset.none()
        self.fields['layer'].empty_label = _('— pick a layer —')
        self.fields['min_objects'].required = False
        self.fields['objects_search'].required = False
        self.fields['panel_mode'].required = False
        self.fields['share_with_respondents'].required = False
        self.is_subquestion = is_subquestion
        # Offered when there is anything to bind: an uploaded layer, or a geo
        # question whose answers can become one (spec survey-editor
        # "Objects on the map source picker").
        geo_exists = bool(survey is not None and conf_settings.MAP_REFERENCE_LAYERS and Question.objects.filter(
            survey_section__survey_header=survey, input_type__in=SHARED_MAP_SOURCE_TYPES,
            parent_question_id__isnull=True).exists())
        if (layer_qs is None or not layer_qs.exists()) and not geo_exists:
            field = self.fields['input_type']
            field.choices = [(value, label) for value, label in field.choices if value != 'layer_objects']
        if section is not None and not section.has_map:
            # A form section has no map — filtering the field's choices both
            # removes the geo group from the type picker (picker_groups_for
            # builds groups from these choices) and rejects a geo input_type
            # server-side as an invalid choice.
            # The picker still shows them, disabled with the reason
            # (`unavailable_types`), so a creator who switched the section to
            # Form learns why there is no map question instead of finding none.
            field = self.fields['input_type']
            reason = _("This section has no map. Switch its Layout to Map to add a map question.")
            field.unavailable_types = {
                value: (label, reason)
                for value, label in field.choices if value in MAP_ONLY_TYPES
            }
            field.choices = [
                (value, label) for value, label in field.choices
                if value not in MAP_ONLY_TYPES
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

        # The modal warns next to the switch when another geo question shares
        # the section, i.e. when the setting would be stored but not honoured.
        self.tap_to_place_blocked = False
        if self.section is not None and self.section.pk:
            from .question_types import GEO_TYPES
            others = self.section.question_set.filter(
                parent_question_id=None, input_type__in=GEO_TYPES)
            if self.instance.pk:
                others = others.exclude(pk=self.instance.pk)
            self.tap_to_place_blocked = others.exists()

        if lock_structure and self.instance.pk:
            self.fields['input_type'].disabled = True
            self.fields['layer'].disabled = True

    def clean_spray_brush(self):
        from .question_types import SPRAY_BRUSH_DEFAULT
        return self.cleaned_data.get('spray_brush') or SPRAY_BRUSH_DEFAULT

    def clean_icon_class(self):
        value = (self.cleaned_data.get('icon_class') or '').strip()
        if not marker_icons.is_valid(value):
            raise forms.ValidationError(_(
                'Use a Font Awesome class (e.g. "fas fa-bus") or a map icon from the catalog '
                '(e.g. "maki:bus", "temaki:bench").'
            ))
        return value

    def clean_display_style(self):
        return self.cleaned_data.get('display_style') or 'default'

    def clean(self):
        cleaned = super().clean()
        # Subtext is rich text for every type now — the block body for `html`,
        # a formatted helper line for the rest — and all of it renders |safe to
        # respondents. This is the one place all three question-saving views
        # pass through, so the allow-list belongs here.
        cleaned['subtext'] = coerce_creator_html(cleaned.get('subtext'))
        # Tap-to-place belongs to a top-level point question only; any other
        # type stores it off whatever is posted (spec point-tap-to-place).
        is_sub = self.is_subquestion or bool(self.instance.parent_question_id_id)
        if cleaned.get('input_type') != 'point' or is_sub:
            cleaned['tap_to_place'] = False
        style = cleaned.get('display_style') or 'default'
        input_type = cleaned.get('input_type')
        # One table decides (question_types.DISPLAY_STYLES_BY_TYPE): a style the
        # type does not accept is stored as the plain rendering.
        if style not in allowed_display_styles(input_type):
            cleaned['display_style'] = 'default'
        if input_type == 'layer_objects':
            layer = cleaned.get('layer')
            if not layer:
                self.add_error('layer', _('Pick the reference layer whose objects this question lists.'))
            elif self.section is not None:
                # One layer once per section (spec layer-objects-question): the
                # question IS the layer's presence on this map, and a second
                # one would draw it twice with two panel lines.
                twin = (Question.objects
                        .filter(survey_section=self.section, input_type='layer_objects',
                                layer=layer, parent_question_id__isnull=True)
                        .exclude(pk=self.instance.pk or 0)
                        .first())
                if twin is not None:
                    self.add_error('layer', _('Already on this section’s map as “%(name)s”.') % {'name': twin.name or _('(unnamed)')})
            # The minimum-objects rule replaces `required` for this type.
            cleaned['required'] = False
            cleaned['min_objects'] = cleaned.get('min_objects') or 0
            cleaned['objects_search'] = cleaned.get('objects_search') or 'auto'
            cleaned['panel_mode'] = cleaned.get('panel_mode') or 'list'
        else:
            # The binding is meaningful for one type only; never keep a stale
            # layer on a question that switched type (PROTECT would then block
            # deleting the layer for no visible reason).
            cleaned['layer'] = None
            cleaned['min_objects'] = 0
            cleaned['objects_search'] = 'auto'
            cleaned['panel_mode'] = 'list'
        # Sharing is a sub-question thing, and only 👍/👎 and text have
        # something other respondents can see.
        if not self.is_subquestion or input_type not in ('thumbs', 'text', 'text_line'):
            cleaned['share_with_respondents'] = False
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


class QuestionGroupForm(forms.ModelForm):
    """A question group's content (change question-groups): title, description,
    display style. The visibility rule and the translations are read by the
    view, like the question form's."""

    class Meta:
        model = QuestionGroup
        fields = ['title', 'description', 'display_style']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 512}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'display_style': forms.RadioSelect,
        }

    def clean_description(self):
        # Creator markup on every respondent page: the same allow-list as
        # question help text (html_sanitize).
        return coerce_creator_html(self.cleaned_data.get('description') or '').strip()

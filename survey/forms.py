from django import forms
from django.forms import widgets
from .models import SurveySection, Question, Answer, INPUT_TYPE_CHOICES, SurveySession
from .question_types import DISPLAY_STYLES_BY_TYPE, allowed_display_styles, section_geo_count, tap_to_place_active
from django.utils import html
import logging
from django import forms
from django.utils.safestring import mark_safe
import re

class HTMLTextWidget(widgets.Widget):
    template_name = 'html_text.html'

    def __init__(self, attrs=None):
        if attrs is not None:
            attrs = attrs.copy()
            self.title = attrs.pop('title', self.title)
            self.subtitle = attrs.pop('subtitle', self.subtitle)

        super().__init__(attrs)

    def get_context(self,name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['title'] = context['widget']['attrs']['title']
        context['widget']['subtitle'] = context['widget']['attrs']['subtitle']
        return context

class HTMLField(forms.Field):
    def __init__(self, *, title, subtitle, **kwargs):
        self.title = title
        self.subtitle = subtitle
        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['title'] = self.title
        attrs['subtitle'] = self.subtitle

        return attrs


class OtherChoiceWidgetMixin:
    """Renders the write-in input under a question's flagged option
    (openspec: other-option-write-in).

    `other_choice` / `other_value` are stamped on the widget instance by the
    form, the way `question_type` and `display_style` are. Without a flagged
    option the widget renders exactly as its stock base class. The option
    template reads `widget.other`; the dropdown reads it from the outer context.
    """
    other_choice = None   # {'code': int, 'label': str} or None
    other_value = ''      # prefilled write-in text (top-level revisit only)

    def _other_state(self, name, selected_values):
        from . import other_option
        if not self.other_choice:
            return None
        code = self.other_choice['code']
        return {
            'name': other_option.field_name(name),
            'code': code,
            'value': self.other_value or '',
            'shown': str(code) in [str(v) for v in (selected_values or [])],
        }

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if self.other_choice and str(value) == str(self.other_choice['code']):
            option['other'] = self._other_state(name, [value] if selected else [])
        return option

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['other'] = self._other_state(name, self.format_value(value))
        return context


class OtherChoiceRadioSelect(OtherChoiceWidgetMixin, forms.RadioSelect):
    option_template_name = 'partials/choice_option_other.html'


class OtherChoiceCheckboxSelectMultiple(OtherChoiceWidgetMixin, forms.CheckboxSelectMultiple):
    option_template_name = 'partials/choice_option_other.html'


class ChoiceDropdownWidget(OtherChoiceWidgetMixin, widgets.Select):
    """Searchable dropdown for choice questions with many options.

    The real form control stays a native <select> (hidden), so validation and
    the submitted value are identical to the radio rendering. The visible part
    is a search input plus a filterable option list.
    """
    template_name = 'choice_dropdown.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        selected_label = ''
        for _, group_choices, _ in context['widget']['optgroups']:
            for option in group_choices:
                if option['selected']:
                    selected_label = option['label']
        context['widget']['selected_label'] = selected_label
        return context


class ChoiceIconGridMixin(OtherChoiceWidgetMixin):
    """Icon grid for choice/multichoice (spec choice-icon-grid).

    One tile per option: the native radio/checkbox wrapped in its label, so the
    posted value, the required check and the write-in behave exactly as in the
    list. `extras` maps a choice code (as str) to its stored `icon`/`group`/`color`;
    consecutive options sharing a group become one run under one heading. The
    write-in field renders once beneath the grid, as in the dropdown. Icon colour:
    the option's own, else the question's (`color`, unless the model default),
    else none — the CSS grey (change icon-grid-color-picker).
    """
    template_name = 'choice_icon_grid.html'
    collapse = False   # single choice collapses to the chosen row after a pick

    def __init__(self, attrs=None, choices=(), extras=None, color=None):
        from .question_types import HEX_COLOR_RE, UNSET_QUESTION_COLOR
        super().__init__(attrs, choices)
        self.extras = extras or {}
        color = (color or '').strip().lower()
        self.color = color if HEX_COLOR_RE.match(color) and color != UNSET_QUESTION_COLOR else ''

    def get_context(self, name, value, attrs):
        from . import marker_icons
        context = super().get_context(name, value, attrs)
        runs = []
        for _, group_choices, _ in context['widget']['optgroups']:
            for option in group_choices:
                extra = self.extras.get(str(option['value']), {})
                icon = extra.get('icon') or ''
                option['icon'] = icon if marker_icons.is_drawable(icon) else ''
                option['icon_color'] = extra.get('color') or self.color or None
                group = (extra.get('group') or '').strip()
                if not runs or runs[-1]['title'] != group:
                    runs.append({'title': group, 'options': []})
                runs[-1]['options'].append(option)
        context['widget']['runs'] = runs
        context['widget']['collapse'] = self.collapse
        return context


class ChoiceIconGridRadio(ChoiceIconGridMixin, forms.RadioSelect):
    collapse = True


class ChoiceIconGridCheckbox(ChoiceIconGridMixin, forms.CheckboxSelectMultiple):
    pass


def _choice_extras(question):
    """`{str(code): {'icon':…, 'group':…, 'color':…}}` for the icon grid; other keys stay out."""
    return {
        str(c.get('code')): {k: c[k] for k in ('icon', 'group', 'color') if isinstance(c.get(k), str)}
        for c in (question.choices or []) if isinstance(c, dict)
    }


class RangeWidget(widgets.Input):
    """Range input with tick marks and min/max labels."""
    input_type = 'range'

    def __init__(self, attrs=None, choices=None):
        super().__init__(attrs)
        self.choices = choices or []

    def render(self, name, value, attrs=None, renderer=None):
        input_html = super().render(name, value, attrs, renderer)

        ticks_html = '<div class="range-ticks">' + ''.join(
            '<span></span>' for _ in self.choices
        ) + '</div>' if self.choices else ''

        if self.choices:
            first = self.choices[0]
            last = self.choices[-1]
            first_label = first["name"] if isinstance(first["name"], str) else (first["name"].get("en") or next(iter(first["name"].values())))
            last_label = last["name"] if isinstance(last["name"], str) else (last["name"].get("en") or next(iter(last["name"].values())))
            labels_html = (
                f'<div class="range-labels">'
                f'<span>{html.escape(str(first_label))}</span>'
                f'<span>{html.escape(str(last_label))}</span></div>'
            )
        else:
            labels_html = ''

        # The wrapper scopes --range-thumb-size, from which the tick and label
        # rows derive their inset. Without it each row guesses separately and
        # they drift apart, which is how the labels came to sit outside the
        # positions the thumb can actually reach.
        return mark_safe(
            '<div class="range-field">' + input_html + ticks_html + labels_html + '</div>'
        )


class LeafletDrawButtonWidget(widgets.Widget):

    draw_type = None
    button_text = None
    template_name = 'leaflet_draw_button.html'

    def __init__(self, attrs=None):
        if attrs is not None:
            attrs = attrs.copy()
            self.draw_type = attrs.pop('type', self.input_type)
            self.title = attrs.pop('title', self.title)
            self.subtitle = attrs.pop('subtitle', self.subtitle)
            self.color = attrs.pop('color', self.color)
            self.icon_class = attrs.pop('icon_class', self.icon_class)
            self.draw_icon_class = attrs.pop('draw_icon_class', self.draw_icon_class)
            self.required = attrs.pop('required', self.required)

        super().__init__(attrs)


    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['title'] = context['widget']['attrs']['title']
        context['widget']['subtitle'] = context['widget']['attrs']['subtitle']
        context['widget']['draw_type'] = self.draw_type
        context['widget']['color'] = context['widget']['attrs']['color']
        context['widget']['icon_class'] = context['widget']['attrs']['icon_class']
        context['widget']['draw_icon_class'] = context['widget']['attrs']['draw_icon_class']
        context['widget']['required'] = context['widget']['required']
        context['widget']['min_features'] = context['widget']['attrs'].get('min_features', '')
        context['widget']['max_features'] = context['widget']['attrs'].get('max_features', '')
        context['widget']['brush_px'] = context['widget']['attrs'].get('brush_px', '')
        context['widget']['max_dots'] = context['widget']['attrs'].get('max_dots', '')
        context['widget']['brush_sizes'] = context['widget']['attrs'].get('brush_sizes', '')
        context['widget']['tap_to_place'] = context['widget']['attrs'].get('tap_to_place', False)
        return context

class PointDrawButtonWidget(LeafletDrawButtonWidget):
    draw_type = 'drawpoint'
    template_name = 'point_draw_button.html'

class LineDrawButtonWidget(LeafletDrawButtonWidget):
    draw_type = 'drawline'
    template_name = 'line_draw_button.html'

class PolygonDrawButtonWidget(LeafletDrawButtonWidget):
    draw_type = 'drawpolygon'
    template_name = 'polygon_draw_button.html'

class SprayDrawButtonWidget(LeafletDrawButtonWidget):
    """`spraycan`: the respondent paints a cloud of dots (spec spraycan-question).
    `data-brush-px` / `data-max-dots` on the button drive the paint mode."""
    draw_type = 'drawspray'
    template_name = 'spray_draw_button.html'


class ShowImageWidget(widgets.Widget):
    template_name = 'show_image.html'

    def __init__(self, attrs=None):
        if attrs is not None:
            attrs = attrs.copy()
            self.image_src = attrs.pop('image_source', self.image_source)

        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['image_source'] = context['widget']['attrs']['image_source']
        context['widget']['subtitle'] = context['widget']['attrs'].get('subtitle', '')

        return context

class LeafletDrawButtonField(forms.Field):
    def __init__(self,*, title, subtitle, color, icon_class, draw_icon_class, min_features=None, max_features=None, brush_px=None, max_dots=None, brush_sizes=None, **kwargs):
        self.title = title
        self.subtitle = subtitle
        self.color = color
        self.icon_class = icon_class
        self.draw_icon_class = draw_icon_class
        self.min_features = min_features
        self.max_features = max_features
        self.brush_px = brush_px
        self.max_dots = max_dots
        self.brush_sizes = brush_sizes

        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['title'] = self.title
        attrs['subtitle'] = self.subtitle
        attrs['color'] = self.color
        attrs['icon_class'] = self.icon_class
        attrs['draw_icon_class'] = self.draw_icon_class
        if self.min_features is not None:
            attrs['min_features'] = self.min_features
        if self.max_features is not None:
            attrs['max_features'] = self.max_features
        if self.brush_px is not None:
            attrs['brush_px'] = self.brush_px
        if self.max_dots is not None:
            attrs['max_dots'] = self.max_dots
        if self.brush_sizes is not None:
            attrs['brush_sizes'] = self.brush_sizes

        return attrs


class FileUploadWidget(widgets.Widget):
    """Respondent file input: async upload, hidden token, states driven by
    file_upload.js. The camera opens on mobile through the capture attribute;
    audio adds a voice recorder when the browser can (progressive enhancement).
    The widget's VALUE is the upload token string — bytes never touch the form.
    """
    template_name = 'file_upload.html'

    ACCEPT = {
        'photo': 'image/*',
        'audio': 'audio/*',
        'document': ('.pdf,.doc,.docx,.xls,.xlsx,.odt,.ods,.txt,.csv,'
                     'application/pdf'),
    }

    def __init__(self, attrs=None, input_type='photo', upload_url='', max_bytes=0,
                 max_files=1, title='', subtitle=''):
        super().__init__(attrs)
        self.input_type = input_type
        self.upload_url = upload_url
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.title = title
        self.subtitle = subtitle

    def value_from_datadict(self, data, files, name):
        # Several hidden inputs share the name — the value is the list.
        try:
            return data.getlist(name)
        except AttributeError:
            return data.get(name)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # Prepopulation hands a list of tokens (several files per question);
        # a lone string is the same thing with one entry.
        tokens = value if isinstance(value, (list, tuple)) else ([value] if value else [])
        items = []
        if tokens:
            from survey.models import Upload
            found = {str(u.token): u for u in Upload.objects.filter(token__in=tokens)}
            for token in tokens:
                upload = found.get(str(token))
                if upload is None:
                    continue
                is_image = upload.content_type.startswith('image/')
                is_audio = (upload.content_type.startswith('audio/')
                            or upload.content_type.startswith('video/'))
                try:
                    if not (is_image or is_audio):
                        # Documents download rather than render. The download
                        # attribute is ignored cross-origin, so the disposition
                        # rides inside the signed URL where S3 honours it.
                        try:
                            href = upload.file.storage.url(
                                upload.file.name,
                                parameters={'ResponseContentDisposition':
                                            'attachment'},
                            )
                        except TypeError:
                            # Filesystem storage takes no parameters; same
                            # origin, the download attribute works there.
                            href = upload.file.url
                    else:
                        href = upload.file.url
                except Exception:
                    href = ''
                items.append({
                    'token': str(upload.token),
                    'name': upload.original_name,
                    'href': href,
                    'is_image': is_image,
                    'is_audio': is_audio,
                })
        context['widget'].update({
            'input_type': self.input_type,
            'accept': self.ACCEPT.get(self.input_type, ''),
            'capture': self.input_type == 'photo',
            'recorder': self.input_type == 'audio',
            'upload_url': self.upload_url,
            'max_bytes': self.max_bytes,
            'max_files': self.max_files,
            'items': items,
            'required': self.is_required,
            'title': self.title,
            'subtitle': self.subtitle,
        })
        return context


class FileUploadField(forms.Field):
    """The form value is a list of tokens; presence is the only validation
    here — everything about each file was validated at upload time."""

    def __init__(self, *, input_type, upload_url, max_bytes, max_files=1,
                 title='', subtitle='', **kwargs):
        kwargs.setdefault('widget', FileUploadWidget(
            input_type=input_type, upload_url=upload_url, max_bytes=max_bytes,
            max_files=max_files, title=title, subtitle=subtitle,
        ))
        super().__init__(**kwargs)
        self.title = title
        self.subtitle = subtitle


class ThumbsWidget(widgets.RadioSelect):
    """👍 / 👎 as two large buttons over a radio pair (spec thumbs-question).

    A RadioSelect under the hood, so the choice machinery — required handling,
    stored `selected_choices`, prepopulation on revisit, visibility rules —
    needs nothing special; only the rendering differs."""
    template_name = 'thumbs.html'


class RankingWidget(widgets.Widget):
    """Drag-to-order list.

    Each item carries a hidden input under the question's field name, so the
    submitted order is simply the DOM order and `request.POST.getlist(code)`
    reads it back with no delimiter to parse. Moving an item moves its input.
    """
    template_name = 'ranking.html'

    def __init__(self, attrs=None):
        self.items = []
        if attrs is not None:
            attrs = attrs.copy()
            self.items = attrs.pop('items', [])

        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        items = context['widget']['attrs'].get('items', [])
        context['widget']['items'] = self._ordered(items, value)
        return context

    @staticmethod
    def _ordered(items, value):
        """Items in the respondent's stored order, if there is one.

        `value` is whatever the form was given as initial: the stored codes on
        a revisit, and nothing on a first view. Anything unrecognised leaves
        the creator's order alone rather than dropping items.
        """
        if not value:
            return items
        wanted = [str(v) for v in value]
        by_code = {str(item['code']): item for item in items}
        if sorted(wanted) != sorted(by_code):
            return items
        return [by_code[code] for code in wanted]


class RankingField(forms.Field):
    def __init__(self, *, items, **kwargs):
        self.items = items

        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['items'] = self.items

        return attrs


class LayerObjectsWidget(widgets.Widget):
    """The "Objects on the map" block: header, search/chips, list container.

    Renders only the shell — the rows come from the layer GeoJSON the map has
    already loaded (base_survey_template.html fills them), so a 300-object
    layer costs no second fetch and no server-rendered list."""
    template_name = 'layer_objects.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        a = context['widget']['attrs']
        for key in ('title', 'subtitle', 'layer_id', 'layer_name', 'question_code', 'min_objects', 'objects_search', 'object_count', 'layer_source', 'panel_mode', 'collects', 'layer_color', 'preview'):
            context['widget'][key] = a.get(key)
        return context


class LayerObjectsField(forms.Field):
    """Display-only: the block collects nothing itself, its sub-questions do."""

    def __init__(self, *, title, subtitle, question, **kwargs):
        self.title = title
        self.subtitle = subtitle
        self.question = question
        kwargs.setdefault('required', False)
        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        from .layers import layer_lite
        layer = layer_lite(self.question)   # never the 10 MB geometry text on a section render
        # Without sub-questions the block only shows the layer: no counter, no
        # minimum (spec layer-objects-question; Question.collects_objects).
        collects = getattr(self.question, 'preview_collects', None)
        if collects is None:
            collects = self.question.collects_objects
        attrs.update({
            # A question that only shows a layer is often left unnamed: the
            # layer's name is the natural label then, never "None".
            'title': self.title or (layer.name if layer else ''),
            'subtitle': self.subtitle,
            # An unsaved layer (live preview of "Respondents' marks on…") has
            # no pk yet; the block still needs a truthy id to render its shell.
            'layer_id': (layer.pk or 'new') if layer else None,
            'layer_name': layer.name if layer else '',
            'layer_color': layer.color if layer else '',
            'question_code': self.question.code,
            'panel_mode': self.question.panel_mode,
            'collects': collects,
            'min_objects': self.question.min_objects if collects else 0,
            'objects_search': self.question.objects_search,
            # A `question` layer's count includes the respondent's own marks
            # and unapproved ones, which their list never shows — no total.
            'object_count': (layer.feature_count if layer and layer.source != 'question' else 0),
            'layer_source': layer.source if layer else '',
        })
        # The editor's live preview asks for a server-rendered panel: real
        # objects instead of the empty shell the client would fill from a
        # map this frame does not have.
        if layer is not None and layer.pk and getattr(self.question, 'preview_panel', False):
            from .layers import preview_panel
            attrs['preview'] = preview_panel(layer)
        return attrs


class ShowImageField(forms.Field):
    def __init__(self, *, image_source, subtitle="", **kwargs):
        self.image_source = image_source
        self.subtitle = subtitle

        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['image_source'] = self.image_source
        attrs['subtitle'] = self.subtitle

        return attrs

def _stamp_tap_to_place(widget, question, geo_count):
    """Mark the point button whose question a map click places (spec
    point-tap-to-place). The browser obeys the mark and never re-counts."""
    if tap_to_place_active(question, geo_count):
        widget.attrs['tap_to_place'] = True


def _stamp_other_choice(widget, question, language, initial=None):
    """Hand the widget its write-in option, if the question has one
    (spec other-option-write-in). `initial` carries the stored text on revisit."""
    from . import other_option
    code = other_option.other_code(question)
    if code is None:
        return
    widget.other_choice = {'code': code, 'label': question.get_choice_name(code, language)}
    widget.other_value = (initial or {}).get(other_option.field_name(question.code), '') or ''


class SurveySectionAnswerForm(forms.Form):

    # Question types whose rendering the creator can pick, and the styles each
    # accepts: ONE table in question_types (spec choice-dropdown-display). `range`
    # was briefly a member and is deliberately out again: a range is the slider —
    # a labelled discrete scale is what `rating` is for. Stored display_style
    # values on range questions are ignored, not rewritten.
    DISPLAY_STYLE_TYPES = tuple(DISPLAY_STYLES_BY_TYPE)

    # Styles that lay out one element per choice, and so need choices to exist.
    CHOICE_BASED_STYLES = ('scale_strip', 'list_pips', 'stars')

    @classmethod
    def resolve_display_style(cls, question, survey_rating_style):
        """Decide how a question is rendered."""
        # Types that do not support display styles must resolve to the plain
        # rendering. Without this every question — text, number, geo — inherits
        # the survey-wide rating style and any consumer keying on the resolved
        # value alone will send a textarea through the scale partials.
        if question.input_type not in cls.DISPLAY_STYLE_TYPES:
            return 'default'

        allowed = allowed_display_styles(question.input_type)
        chosen = question.display_style if question.display_style in allowed and question.display_style != 'default' else None
        if question.input_type == 'rating':
            return chosen or survey_rating_style
        return chosen or 'default'

    @classmethod
    def _get_form_from_input_type(cls, input_type, required, question, label, sublabel, color, icon_class, image_source, language=None, display_style='default'):

        if input_type == 'text':
            return forms.CharField(widget=forms.Textarea, label=label, required=required)

        elif input_type == 'text_line':
            return forms.CharField(widget=forms.TextInput, label=label, required=required)

        elif input_type == 'number':
            return forms.CharField(widget=forms.NumberInput, label=label, required=required)

        elif input_type == 'choice':
            choices = [(c["code"], question.get_choice_name(c["code"], language)) for c in (question.choices or [])]
            if display_style == 'icon_grid':
                widget = ChoiceIconGridRadio(extras=_choice_extras(question), color=question.color)
            else:
                widget = ChoiceDropdownWidget if display_style == 'dropdown' else OtherChoiceRadioSelect
            return forms.ChoiceField(widget=widget, choices=choices, label=label, required=required)

        elif input_type == 'multichoice':
            choices = [(c["code"], question.get_choice_name(c["code"], language)) for c in (question.choices or [])]
            if display_style == 'icon_grid':
                widget = ChoiceIconGridCheckbox(extras=_choice_extras(question), color=question.color)
            else:
                widget = OtherChoiceCheckboxSelectMultiple
            return forms.MultipleChoiceField(
                widget=widget,
                choices=choices,
                label=label,
                required=required,
            )

        elif input_type == 'range':
            choices = question.choices or []

            codes = [c["code"] for c in choices]
            minimum = min(codes) if codes else 0
            maximum = max(codes) if codes else 10
            return forms.IntegerField(widget=RangeWidget(attrs={'step': '1', 'min': str(minimum), 'max': str(maximum)}, choices=choices), label=label, required=required)

        elif input_type == 'point':
            draw_icon_class = icon_class if icon_class else "fas fa-map-marker-alt"
            vs = question.validation_settings or {}
            return LeafletDrawButtonField(widget=PointDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required, min_features=vs.get('min_features'), max_features=vs.get('max_features'))

        elif input_type == 'line':
            draw_icon_class = icon_class if icon_class else "fas fa-route"
            vs = question.validation_settings or {}
            return LeafletDrawButtonField(widget=LineDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required, min_features=vs.get('min_features'), max_features=vs.get('max_features'))

        elif input_type == 'polygon':
            draw_icon_class = icon_class if icon_class else "fas fa-draw-polygon"
            vs = question.validation_settings or {}
            return LeafletDrawButtonField(widget=PolygonDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required, min_features=vs.get('min_features'), max_features=vs.get('max_features'))

        elif input_type == 'spraycan':
            from survey.question_types import SPRAY_BRUSH_PX, SPRAY_BRUSH_DEFAULT
            draw_icon_class = icon_class if icon_class else "fas fa-spray-can"
            brush_px = SPRAY_BRUSH_PX.get(question.spray_brush, SPRAY_BRUSH_PX[SPRAY_BRUSH_DEFAULT])
            # Optional creator cap; absent = unlimited (no data-max-dots attribute).
            max_dots = (question.validation_settings or {}).get('max_dots')
            if not isinstance(max_dots, int) or max_dots <= 0:
                max_dots = None
            # One cloud per respondent: no min/max features (spec spraycan-question).
            # The creator's size is the default; the respondent can switch in the
            # paint toolbar, so the whole size map rides on the button.
            import json as _json
            return LeafletDrawButtonField(widget=SprayDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required, brush_px=brush_px, max_dots=max_dots, brush_sizes=_json.dumps(SPRAY_BRUSH_PX))

        elif input_type == 'image':
            return ShowImageField(widget=ShowImageWidget, label=False, image_source=image_source,
                                  subtitle=sublabel)

        elif input_type in ('photo', 'audio', 'document'):
            from django.conf import settings as conf_settings
            from django.urls import reverse
            from .uploads import effective_max_bytes
            if not getattr(conf_settings, 'FILE_UPLOAD_QUESTIONS', False):
                # Kill switch: stored file questions render nothing for the
                # respondent; the rest of the section works (fail open).
                return None
            upload_url = reverse(
                'survey_upload',
                kwargs={'survey_slug': str(question.survey_section.survey_header.uuid)},
            )
            from .uploads import max_files_for
            return FileUploadField(
                input_type=input_type, upload_url=upload_url,
                max_bytes=effective_max_bytes(question),
                max_files=max_files_for(question),
                label=label, required=required, title=label, subtitle=sublabel,
            )

        elif input_type == 'rating':
            # Stars fall back to five numbered steps when the creator never
            # defined choices — the style is picked far more often than a
            # choice list is written.
            source = question.star_choices() if display_style == 'stars' else (question.choices or [])
            choices = [(c["code"], question.get_choice_name(c["code"], language) or str(c["code"]))
                       for c in source]
            return forms.ChoiceField(widget=forms.RadioSelect(attrs={'class': 'form-check-inline', 'style': 'margin-right:0;'}), choices=choices, label=label, required=required)

        elif input_type == 'thumbs':
            # Fixed two-choice list; names are the export values (`up`/`down`),
            # the widget template draws the icons and localised labels.
            choices = [(c["code"], c["name"]) for c in question.thumbs_choices()]
            return forms.ChoiceField(widget=ThumbsWidget, choices=choices, label=label, required=required)

        elif input_type == 'layer_objects':
            # Collects nothing itself: the list block and the popup carry the
            # sub-question forms (spec layer-objects-question). The field is
            # display-only so the section form has a slot to render the block in.
            return LayerObjectsField(widget=LayerObjectsWidget, label=False, title=label,
                                     subtitle=sublabel, question=question)

        elif input_type == 'ranking':
            # `initial` carries the respondent's stored order when they navigate
            # back; otherwise the creator's order stands.
            return RankingField(widget=RankingWidget, label=label, required=required,
                                items=question.ranking_items(language))

        elif input_type == 'datetime':
            return forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), label=label, required=required)

        elif input_type == "html":
            return HTMLField(widget=HTMLTextWidget, label=False, title = label, subtitle=sublabel)
        else:
            return forms.CharField(widget=forms.Textarea)
    

    @classmethod
    def single_question_form(cls, question, language=None):
        """One-field form for `question`, which may be unsaved.

        The field is built by the same machinery `__init__` uses for a whole
        section, so the render is the respondent's render — this is what the
        editor's preview endpoints ask for, including for a question that only
        exists as the current state of the New Question dialog.
        """
        survey_rating_style = question.survey_section.survey_header.get_default_rating_display_style()
        resolved_style = cls.resolve_display_style(question, survey_rating_style)

        form = forms.Form()
        field = cls._get_form_from_input_type(
            question.input_type, question.required, question,
            question.get_translated_name(language),
            question.get_translated_subtext(language) if question.subtext else "",
            question.color, question.icon_class,
            question.image.url if question.image else None,
            language, display_style=resolved_style,
        )
        field.widget.question_type = question.input_type
        field.widget.display_style = resolved_style
        # Ordinary questions render their subtext from the section template,
        # between the label and the input. Geo types and html carry it inside
        # their own widget instead, so they are left out here.
        field.widget.question_subtext = (
            question.get_translated_subtext(language) if question.subtext else "")
        _stamp_other_choice(field.widget, question, language)
        if resolved_style == 'stars':
            # The star partial paints from these; resolved here so the two form
            # paths (whole section, single question) cannot disagree.
            field.widget.star_icon = question.star_icon()
            field.widget.star_color = question.star_color()
        if question.input_type == 'point':
            _stamp_tap_to_place(field.widget, question,
                                section_geo_count(question.survey_section, with_question=question))
        form.fields[question.code] = field
        return form

    def __init__(self, initial, section, question, survey_session_id, language=None, questions_override=None, *args, surface=None, **kwargs):
        super().__init__(*args, initial=initial, **kwargs)
        from .question_types import SURFACE_RESPONDENT, SURFACE_OPERATOR, audience_allows
        from .visibility import operator_only
        # Which page this form is for (spec question-audience): pop-up items whose
        # audience excludes it are left out; on the operator page (spec
        # operator-entry) only operator-only questions keep `required`.
        self.surface = surface or SURFACE_RESPONDENT

        section = section
        survey_session_id = survey_session_id
        self.language = language

        if question == None:
            # The view may pass the visibility-filtered subset; None keeps the
            # section's full list (single-question/sub-question paths, editor).
            questions = section.questions() if questions_override is None else questions_override
        else:
            questions = [
                sub for sub in question.subQuestions()
                if audience_allows(sub.audience, self.surface)
                and (not sub.group_id or audience_allows(sub.group.audience, self.surface))
            ]
        # Kept for field_runs (change question-groups): the groups this form's
        # questions may sit in — the section's top level, or one pop-up.
        self._run_questions = list(questions)
        self._run_parent = question
        self._run_section = section

        survey_rating_style = section.survey_header.get_default_rating_display_style()
        # Counted over the whole section, not the visibility-filtered subset:
        # the tap-to-place rule is static (spec point-tap-to-place). Pop-up
        # forms hold no geo questions, so they skip the query.
        geo_count = section_geo_count(section) if self._run_parent is None else 0

        for question in questions:

            #add question to field
            field_name = question.code
            field_label = question.get_translated_name(language)
            field_sublabel = question.get_translated_subtext(language) if question.subtext else ""
            field_color = question.color
            field_icon_class = question.icon_class
            image_source = question.image.url if question.image else None

            # Resolved before the field is built, because for `range` it
            # decides which kind of field to build.
            resolved_style = self.resolve_display_style(question, survey_rating_style)

            required = question.required
            if self.surface == SURFACE_OPERATOR and required and not operator_only(question):
                required = False  # a blank on paper stays a blank
            built_field = self._get_form_from_input_type(question.input_type, required, question, field_label, field_sublabel, field_color, field_icon_class, image_source, language, display_style=resolved_style)
            if built_field is None:
                # A kill-switched type renders nothing; the section must keep
                # working without it (fail open).
                continue
            self.fields[field_name] = built_field
            self.fields[field_name].widget.question_type = question.input_type
            self.fields[field_name].widget.display_style = resolved_style
            self.fields[field_name].widget.question_subtext = field_sublabel
            _stamp_other_choice(self.fields[field_name].widget, question, language, initial)
            if resolved_style == 'stars':
                self.fields[field_name].widget.star_icon = question.star_icon()
                self.fields[field_name].widget.star_color = question.star_color()
            if question.input_type == 'point':
                _stamp_tap_to_place(self.fields[field_name].widget, question, geo_count)


    @property
    def field_runs(self):
        """Bound fields in question order, split into group runs for
        partials/question_fields.html: [{'group', 'title', 'description',
        'fields'}], `group` None for ungrouped questions. A group none of whose
        questions has a field here (hidden server-side, kill-switched type) is
        not rendered at all."""
        if getattr(self, 'runs_override', None) is not None:
            # The editor's group preview renders one unsaved group (editor_group_views).
            return self.runs_override
        from .groups import group_runs, groups_for
        parent = self._run_parent
        if parent is not None and parent.pk is None:
            groups = []
        else:
            groups = groups_for(self._run_section, parent)
        runs = []
        for group, members in group_runs(self._run_questions, groups):
            fields = [self[q.code] for q in members if q.code in self.fields]
            if not fields:
                continue
            runs.append({
                'group': group,
                'title': group.get_translated_title(self.language) if group else '',
                'description': group.get_translated_description(self.language) if group else '',
                'fields': fields,
            })
        return runs

    def save(self):
        pass
        #delete old data if exists
        '''
        questions = Question.objects.filter(survey_section=self.instance)
        for question in questions:
            Answer.objects.filter(question=question, survey_session=self.survey_session).delete()

        for answer in self.cleaned_data:
            Answer.objects.create(
                question=question,
                survey_session=self.survey_session,
                )
        '''











from django import forms
from django.forms import widgets
from .models import SurveySection, Question, Answer, INPUT_TYPE_CHOICES, SurveySession
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

        return context

class LeafletDrawButtonField(forms.Field):
    def __init__(self,*, title, subtitle, color, icon_class, draw_icon_class, **kwargs):
        self.title = title
        self.subtitle = subtitle
        self.color = color
        self.icon_class = icon_class
        self.draw_icon_class = draw_icon_class

        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['title'] = self.title
        attrs['subtitle'] = self.subtitle
        attrs['color'] = self.color
        attrs['icon_class'] = self.icon_class
        attrs['draw_icon_class'] = self.draw_icon_class

        return attrs

class ShowImageField(forms.Field):
    def __init__(self, *, image_source, **kwargs):
        self.image_source = image_source

        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['image_source'] = self.image_source

        return attrs

class SurveySectionAnswerForm(forms.Form):

    # Question types whose rendering the creator can pick. Membership, rather
    # than a chain of equality tests, so the next type to gain display styles
    # is one entry here and in the editor's gate.
    DISPLAY_STYLE_TYPES = ('rating', 'range')

    # Styles that lay out one element per choice, and so need choices to exist.
    CHOICE_BASED_STYLES = ('scale_strip', 'list_pips')

    @classmethod
    def resolve_display_style(cls, question, survey_rating_style):
        """Decide how a question is rendered.

        For `range`, `default` means the slider and deliberately does not
        inherit the survey-wide rating style — inheriting would silently
        restyle every existing range question the first time this deploys.

        A choice-based style with no choices to lay out falls back to the
        slider rather than rendering an empty control. 28% of range questions
        in production have no choices, so this is a live path.
        """
        # Types that do not support display styles must resolve to the plain
        # rendering. Without this every question — text, number, geo — inherits
        # the survey-wide rating style and any consumer keying on the resolved
        # value alone will send a textarea through the scale partials.
        if question.input_type not in cls.DISPLAY_STYLE_TYPES:
            return 'default'

        chosen = question.display_style if question.display_style in cls.CHOICE_BASED_STYLES else None

        if question.input_type == 'range':
            if chosen and not question.choices:
                return 'default'
            return chosen or 'default'

        return chosen or survey_rating_style

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
            return forms.ChoiceField(widget=forms.RadioSelect, choices=choices, label=label, required=required)

        elif input_type == 'multichoice':
            choices = [(c["code"], question.get_choice_name(c["code"], language)) for c in (question.choices or [])]
            return forms.MultipleChoiceField(
                widget=forms.CheckboxSelectMultiple,
                choices=choices,
                label=label,
                required=required,
            )

        elif input_type == 'range':
            choices = question.choices or []

            # The choice-based styles render one radio per choice, which an
            # IntegerField cannot supply. The stored value is unaffected: the
            # save path keys on question.input_type, not on the widget.
            if display_style in cls.CHOICE_BASED_STYLES and choices:
                return forms.ChoiceField(
                    widget=forms.RadioSelect(),
                    choices=[(c["code"], question.get_choice_name(c["code"], language)) for c in choices],
                    label=label,
                    required=required,
                )

            codes = [c["code"] for c in choices]
            minimum = min(codes) if codes else 0
            maximum = max(codes) if codes else 10
            return forms.IntegerField(widget=RangeWidget(attrs={'step': '1', 'min': str(minimum), 'max': str(maximum)}, choices=choices), label=label, required=required)

        elif input_type == 'point':
            draw_icon_class = icon_class if icon_class else "fas fa-map-marker-alt"
            return LeafletDrawButtonField(widget=PointDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required)

        elif input_type == 'line':
            draw_icon_class = icon_class if icon_class else "fas fa-route"
            return LeafletDrawButtonField(widget=LineDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required)

        elif input_type == 'polygon':
            draw_icon_class = icon_class if icon_class else "fas fa-draw-polygon"
            return LeafletDrawButtonField(widget=PolygonDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class=draw_icon_class, required=required)

        elif input_type == 'image':
            return ShowImageField(widget=ShowImageWidget, label=False, image_source=image_source)

        elif input_type == 'rating':
            choices = [(c["code"], question.get_choice_name(c["code"], language)) for c in (question.choices or [])]
            return forms.ChoiceField(widget=forms.RadioSelect(attrs={'class': 'form-check-inline', 'style': 'margin-right:0;'}), choices=choices, label=label, required=required)

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
        form.fields[question.code] = field
        return form

    def __init__(self, initial, section, question, survey_session_id, language=None, *args, **kwargs):
        super().__init__(*args, initial=initial, **kwargs)

        section = section
        survey_session_id = survey_session_id
        self.language = language

        if question == None:
            questions = section.questions()
        else:
            questions = question.subQuestions()

        survey_rating_style = section.survey_header.get_default_rating_display_style()

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

            self.fields[field_name] = self._get_form_from_input_type(question.input_type, question.required, question, field_label, field_sublabel, field_color, field_icon_class, image_source, language, display_style=resolved_style)
            self.fields[field_name].widget.question_type = question.input_type
            self.fields[field_name].widget.display_style = resolved_style


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











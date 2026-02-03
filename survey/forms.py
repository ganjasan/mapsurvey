from django import forms
from django.forms import widgets
from .models import SurveySection,Question, Answer, INPUT_TYPE_CHOICES, SurveySession, OptionGroup
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

    def _get_form_from_input_type(self, input_type, required, option_group, label, sublabel, color, icon_class, image_source, language=None):

        if input_type == 'text':
            return forms.CharField(widget=forms.Textarea, label=label, required=required)

        elif input_type == 'text_line':
            return forms.CharField(widget=forms.TextInput, label=label, required=required)

        elif input_type == 'number':
            return forms.CharField(widget=forms.NumberInput, label=label, required=required)

        elif input_type == 'choice':
            choices = [(choice.code, choice.get_translated_name(language)) for choice in option_group.choices()]
            return forms.ChoiceField(widget=forms.RadioSelect, choices=choices, label=label, required=required)

        elif input_type == 'multichoice':
            choices = [(choice.code, choice.get_translated_name(language)) for choice in option_group.choices()]
            return forms.MultipleChoiceField(
                widget=forms.CheckboxSelectMultiple,
                choices=choices,
                label=label,
                required=required,
            )

        elif input_type == 'range':
            int_choices = [ int(c.name) for c in option_group.choices()]
            minimum = min(int_choices)
            maximum = max(int_choices)
            return forms.IntegerField(widget=forms.NumberInput(attrs={'type':'range', 'step': '1', 'min':str(minimum), 'max':str(maximum)}), label=label, required=required)

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
            choices = [(choice.code, choice.get_translated_name(language)) for choice in option_group.choices()]
            return forms.ChoiceField(widget=forms.RadioSelect(attrs={'class': 'form-check-inline', 'style': 'margin-right:0;'}), choices=choices, label=label, required=required)

        elif input_type == "html":
            return HTMLField(widget=HTMLTextWidget, label=False, title = label, subtitle=sublabel)
        else:
            return forms.CharField(widget=forms.Textarea)
    

    def __init__(self, initial, section, question, survey_session_id, language=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        section = section
        survey_session_id = survey_session_id
        self.language = language

        if question == None:
            questions = section.questions()
        else:
            questions = question.subQuestions()

        for question in questions:

            #add question to field
            field_name = question.code
            field_label = question.get_translated_name(language)
            field_sublabel = question.get_translated_subtext(language) if question.subtext else ""
            field_color = question.color
            field_icon_class = question.icon_class
            image_source = question.image.url if question.image else None

            self.fields[field_name] = self._get_form_from_input_type(question.input_type, question.required, question.option_group, field_label, field_sublabel, field_color, field_icon_class, image_source, language)


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











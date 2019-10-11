from django import forms
from django.forms import widgets
from .models import SurveySection,Question, Answer, INPUT_TYPE_CHOICES, SurveySession, OptionGroup
from django.utils import html
import logging
from django import forms
from django.utils.safestring import mark_safe
import re


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

        super().__init__(attrs)


    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['title'] = context['widget']['attrs']['title']
        context['widget']['subtitle'] = context['widget']['attrs']['subtitle']
        context['widget']['draw_type'] = self.draw_type
        context['widget']['color'] = context['widget']['attrs']['color']
        context['widget']['icon_class'] = context['widget']['attrs']['icon_class']
        context['widget']['draw_icon_class'] = context['widget']['attrs']['draw_icon_class']
        
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


class SurveySectionAnswerForm(forms.Form):

    def _get_form_from_input_type(self, input_type, required,  option_group, label, sublabel, color, icon_class):

        if input_type == 'text':
            return forms.CharField(widget=forms.Textarea, label=label, required = required)

        if input_type == 'number':
            return forms.CharField(widget=forms.NumberInput, label=label, required = required)

        elif input_type == 'choice':
            return forms.ChoiceField(widget=forms.RadioSelect, choices=[(choice.code, choice.name) for choice in option_group.choices()], label=label, required=required)

        elif input_type == 'multichoice':
            return forms.MultipleChoiceField(
                widget=forms.CheckboxSelectMultiple,
                choices = [(choice.code, choice.name) for choice in option_group.choices()],
                label = label,
                required = required,
            )

        elif input_type == 'range':
            int_choices = [ int(c.name) for c in option_group.choices()]
            minimum = min(int_choices)
            maximum = max(int_choices)
            return forms.IntegerField(widget=forms.NumberInput(attrs={'type':'range', 'step': '1', 'min':str(minimum), 'max':str(maximum)}), label=label)

        elif input_type == 'point':
            return LeafletDrawButtonField(widget=PointDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class="fas fa-map-marker-alt")

        elif input_type == 'line':
            return LeafletDrawButtonField(widget=LineDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class="")

        elif input_type == 'polygon':
            return LeafletDrawButtonField(widget=PolygonDrawButtonWidget, label=False, title = label, subtitle = sublabel, color=color, icon_class=icon_class, draw_icon_class="fas fa-draw-polygon")

        else:
            return forms.CharField(widget=forms.Textarea)
    

    def __init__(self, initial, section, question, survey_session_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        section = section
        survey_session_id = survey_session_id

        if question == None:
            questions = section.questions()
        else:
            questions = question.subQuestions()

        for question in questions:

            #add question to field
            field_name = question.code
            field_label = question.name
            field_sublabel = question.subtext
            field_color = question.color
            field_icon_class = question.icon_class

            self.fields[field_name] = self._get_form_from_input_type(question.input_type, question.required, question.option_group, field_label, field_sublabel, field_color, field_icon_class)


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











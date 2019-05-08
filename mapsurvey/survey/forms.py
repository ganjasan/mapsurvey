from django import forms
from django.forms import widgets
from .models import SurveySection,Question, Answer, INPUT_TYPE_CHOICES, SurveySession, OptionGroup
from django.utils import html
import logging

class LeafletDrawButtonWidget(widgets.Widget):

    draw_type = None
    button_text = None
    template_name = 'leaflet_draw_button.html'

    def __init__(self, attrs=None):
        if attrs is not None:
            attrs = attrs.copy()
            self.draw_type = attrs.pop('type', self.input_type)
            self.button_text = attrs.pop('button_text', self.button_text)

        super().__init__(attrs)


    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['button_text'] = context['widget']['attrs']['button_text']
        context['widget']['draw_type'] = self.draw_type

        print(context['widget'])
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
    def __init__(self, *, button_text, **kwargs):
        self.button_text = button_text

        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs['button_text'] = self.button_text

        return attrs



class SurveySectionAnswerForm(forms.Form):

    def _get_form_from_input_type(self, input_type, option_group, label):

        if input_type == 'text':
            return forms.CharField(widget=forms.Textarea, label=label)

        elif input_type == 'choice':
            return forms.ChoiceField(widget=forms.RadioSelect, choices=[(choice.code, choice.name) for choice in option_group.choices()], label=label)

        elif input_type == 'multichoice':
            return forms.MultipleChoiceField(
                required=False,
                widget=forms.CheckboxSelectMultiple,
                choices = [(choice.code, choice.name) for choice in option_group.choices()],
                label = label,
            )

        elif input_type == 'point':
            return LeafletDrawButtonField(widget=PointDrawButtonWidget, button_text=label, label=False)

        elif input_type == 'line':
            return LeafletDrawButtonField(widget=LineDrawButtonWidget, button_text = label, label=False)

        elif input_type == 'polygon':
            return LeafletDrawButtonField(widget=PolygonDrawButtonWidget, button_text = label, label=False)

        else:
            return forms.CharField(widget=forms.Textarea)
    

    def __init__(self, initial, instance, survey_session_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        section = instance
        survey_session_id = survey_session_id


        questions = section.questions()

        for question in questions:

            #try to get answers if exists
            #question['answers'] = Answer.objects.filter(question=question, survey_session=self.survey_session)

            #add question to field
            field_name = question.code
            field_label = question.name
            self.fields[field_name] = self._get_form_from_input_type(question.input_type, question.option_group, field_label)
            
            #fill fields if answer exists TODO
            '''
            try:
                self.initial[field_name] = question['answers']
            except Exception:
                #TODO
            '''


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











from django import forms
from .models import SurveyHeader, SurveySection, Question, Organization


class SurveyHeaderForm(forms.ModelForm):
    class Meta:
        model = SurveyHeader
        fields = ['name', 'organization', 'redirect_url', 'available_languages', 'visibility', 'thanks_html']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'survey_name'}),
            'redirect_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#'}),
            'available_languages': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '["en", "ru"]'}),
            'visibility': forms.Select(attrs={'class': 'form-control'}),
            'thanks_html': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '{"en": "<h1>Thanks!</h1>"}'}),
        }


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

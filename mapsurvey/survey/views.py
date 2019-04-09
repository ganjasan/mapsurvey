from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponse
from .models import Survey, Question, SurveySession, Answer
from datetime import datetime
from django import forms
from django.views.generic import UpdateView
from leaflet.forms.widgets import LeafletWidget


class AnswerForm(forms.ModelForm):
	class Meta:
		model = Answer
		fields = ('question', 'geometry')
		widgets = {'geometry': LeafletWidget()}

class EditAnswerForm(UpdateView):
	model = Answer
	form_class = AnswerForm
	template_name = 'answer.html'

	success_url = '../Q2/'


	def get_object(self):
		survey = Survey.objects.get(url_name=self.kwargs['survey_name'])

		#если сессия на задана, то создать запись сессии
		if  not self.request.session.get('survey_session_id'):
			survey_session = SurveySession(survey=survey)
			survey_session.save()
			self.request.session['survey_session_id'] = survey_session.id
		
		question = Question.objects.get(Q(survey = survey) & Q(code = self.kwargs['question_code']))
		survey_session = SurveySession.objects.get(pk = self.request.session['survey_session_id'])

		answer = Answer(survey_session=survey_session, question=question)
		answer.save()
		return  answer

def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

def survey_list(request):
	survey_list = Survey.objects.all()
	context = {'survey_list': survey_list}
	return render(request, 'survey_list.html', context)

def survey(request, survey_name):
	if request.session.get('survey_session_id'):
		del request.session['survey_session_id']

	survey = Survey.objects.get(url_name=survey_name)
	context = {'survey': survey}
	return render(request, 'survey_template.html', context)

def question(request, survey_name, question_code):

	survey = Survey.objects.get(url_name=survey_name)

	#если сессия на задана, то создать запись сессии
	if  not request.session.get('survey_session_id'):
		survey_session = SurveySession(survey=survey)
		survey_session.save()
		request.session['survey_session_id'] = survey_session.id
		
		
	question = Question.objects.get(Q(survey=survey) & Q(code=question_code))

	context = {'survey': survey, 'question': question, 'session_id': request.session['survey_session_id']}
	return render(request, 'question_template.html', context)




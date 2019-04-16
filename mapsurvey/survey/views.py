from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponse
from .models import SurveyHeader, SurveySession, SurveySection, Answer, OptionGroup, Question, OptionChoice
#from .models import Survey, Question, SurveySession, Answer
from datetime import datetime
from django import forms
from django.views.generic import UpdateView
from leaflet.forms.widgets import LeafletWidget
from .forms import SurveySectionAnswerForm
from django.http import HttpResponseRedirect

def index(request):
    return HttpResponse("Hello, world")

def survey_list(request):
	survey_list = SurveyHeader.objects.all()
	context = {'survey_list': survey_list}
	return render(request, 'survey_list.html', context)

def survey_header(request, survey_name):
	if request.session.get('survey_session_id'):
		del request.session['survey_session_id']

	survey = SurveyHeader.objects.get(name=survey_name)
	context = {'survey': survey, 'section': survey.start_section()}

	return render(request, 'survey_header.html', context)

def survey_section(request, survey_name, section_name):
	
	survey = SurveyHeader.objects.get(name=survey_name)

	#если сессия на задана, то создать запись сессии
	if  not request.session.get('survey_session_id'):
		survey_session = SurveySession(survey=survey)
		survey_session.save()
		request.session['survey_session_id'] = survey_session.id

	section = SurveySection.objects.get(Q(survey_header=survey) & Q(name=section_name))

	if request.method == 'POST':
		#form = SurveySectionAnswerForm(initial=request.POST, instance=section, survey_session_id=request.session['survey_session_id'])
		#save data to answers
		section_questions = section.questions()
		survey_session = SurveySession.objects.get(pk=request.session['survey_session_id'])
		for question in section_questions:
			result = request.POST[question.code]
			answer = Answer(survey_session=survey_session, question=question)
			answer.save()

			if question.option_group == OptionGroup.objects.get(name='other'):
				if question.input_type == "text":
					pass
				elif question.input_type == "number":
					pass
				elif question.input_type == "point":
					pass
				elif question.input_type == "line":
					pass
				elif question.input_type == "polygon":
					pass
				else:
					pass

			else:
				for result_answer in result:
					choice = OptionChoice.objects.get(Q(option_group=question.option_group) & Q(code=result_answer))
					answer.choice.add(choice)
					answer.save()

			

		
		return HttpResponseRedirect('../'+section.next_section.name)

	else:
		form = SurveySectionAnswerForm(initial={}, instance=section, survey_session_id=request.session['survey_session_id'] )

	return render(request, 'survey_section.html', {'form': form, 'survey':survey, 'section':section})

	#context = {'survey': survey, 'section': section, 'questions': section.questions(), 'session_id': request.session['survey_session_id']}

	
'''
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
		return  answer



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

	

		
		
	question = Question.objects.get(Q(survey=survey) & Q(code=question_code))

	context = {'survey': survey, 'question': question, 'session_id': request.session['survey_session_id']}
	return render(request, 'question_template.html', context)

'''


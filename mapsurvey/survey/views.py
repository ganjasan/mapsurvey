from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponse
from .models import SurveyHeader, SurveySession, SurveySection, Answer, OptionGroup, Question, OptionChoice
from datetime import datetime
from django import forms
from django.views.generic import UpdateView
from .forms import SurveySectionAnswerForm
from django.http import HttpResponseRedirect
from django.core import serializers
import geojson
from django.contrib.gis.geos import GEOSGeometry
import sys

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
		form = SurveySectionAnswerForm(initial=request.POST, instance=section, survey_session_id=request.session['survey_session_id'])

		#save data to answers
		section_questions = section.questions()
		survey_session = SurveySession.objects.get(pk=request.session['survey_session_id'])

		for question in section_questions:
			result = request.POST.getlist(question.code)
			print(result)

			if (result != []):
				if question.option_group == OptionGroup.objects.get(name='other'):
					result = result[0]
					if (question.input_type in ['point', 'line', 'polygon']):
						geostr_list = result.split('|')
						for geostr in geostr_list:
							if geostr != '':
								answer = Answer(survey_session=survey_session, question=question)

								gj = geojson.loads(geostr)
								gj = geojson.dumps(gj['geometry'])
								resultToSave = GEOSGeometry(gj)

								if question.input_type == "point":
									answer.point = resultToSave
								elif question.input_type == "line":
									answer.line = resultToSave
								elif question.input_type == "polygon":
									answer.polygon = resultToSave

								answer.save()

					else:
						answer = Answer(survey_session=survey_session, question=question)

						if question.input_type == "text":
							answer.text = result
						elif question.input_type == "number":
							answer.numeric = float(result)
						else:
							pass

						answer.save()

				else:
					answer = Answer(survey_session=survey_session, question=question)
					answer.save()
					for result_answer in result:
						choice = OptionChoice.objects.get(Q(option_group=question.option_group) & Q(code=result_answer))
						answer.choice.add(choice)

					answer.save()

		next_page = ("../" + section.next_section.name) if section.next_section else survey.redirect_url
		return HttpResponseRedirect(next_page)

	else:
		form = SurveySectionAnswerForm(initial={}, instance=section, survey_session_id=request.session['survey_session_id'] )

	return render(request, 'survey_section.html', {'form': form, 'survey':survey, 'section':section})


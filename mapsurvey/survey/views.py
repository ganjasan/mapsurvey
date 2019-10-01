from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from .models import SurveyHeader, SurveySession, SurveySection, Answer, OptionGroup, Question, OptionChoice
from datetime import datetime
from django import forms
from django.views.generic import UpdateView
from .forms import SurveySectionAnswerForm
from django.http import HttpResponseRedirect
from django.core.serializers import serialize
import geojson
from django.contrib.gis.geos import GEOSGeometry
import sys
from io import BytesIO
from zipfile import ZipFile

def index(request):
	if not request.user.is_authenticated:
		return redirect('/accounts/login/')

	return redirect('/editor')

@login_required
def editor(request):
	survey_list = SurveyHeader.objects.all()
	context = {
		"survey_headers": survey_list,
	}
	return render(request, "editor.html", context)

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
		form = SurveySectionAnswerForm(initial=request.POST, section=section, question=None, survey_session_id=request.session['survey_session_id'])

		#save data to answers
		section_questions = section.questions()
		survey_session = SurveySession.objects.get(pk=request.session['survey_session_id'])

		for question in section_questions:
			result = request.POST.getlist(question.code)
			print(result)
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
								geometry = geojson.dumps(gj['geometry'])
								resultToSave = GEOSGeometry(geometry)

								if question.input_type == "point":
									answer.point = resultToSave
								elif question.input_type == "line":
									answer.line = resultToSave
								elif question.input_type == "polygon":
									answer.polygon = resultToSave

								answer.save()

								#сохранить properties как ответы наследники
								properties = gj['properties'];
								for key, value in properties.items():
									if key != 'question_id':
										sub_question = Question.objects.get(code=key)
										sub_answer = Answer(survey_session=survey_session, question=sub_question, parent_answer_id = answer)
										if sub_question.option_group == OptionGroup.objects.get(name='other'):
											if sub_question.input_type == 'text':
												sub_answer.text = value
											elif sub_question.input_type == 'number':
												sub_answer.numeric = float(value)
											else:
												pass
										else:
											sub_answer.save()
											for result_answer in value:
												choice = OptionChoice.objects.get(Q(option_group=sub_question.option_group) & Q(code=result_answer))
												sub_answer.choice.add(choice)

										sub_answer.save()


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
		form = SurveySectionAnswerForm(initial={}, section=section, question=None, survey_session_id=request.session['survey_session_id'])

		questions = section.questions();

		
		#subquestion_form = SurveySectionAnswerForm(initial={}, section=section, question=questions[0], survey_session_id=request.session['survey_session_id']).as_p()
		
		subquestions_forms = {}
		for question in questions:
			subquestions_forms[question.code] = SurveySectionAnswerForm(initial={}, section=section, question=question, survey_session_id=request.session['survey_session_id']).as_p()
		


	return render(request, 'survey_section.html', {'form': form, 'subquestions_forms':subquestions_forms, 'survey':survey, 'section':section})

@login_required
def download_data(request, survey_name):
	in_memory = BytesIO()
	zip = ZipFile(in_memory, "a")

	survey = SurveyHeader.objects.get(name=survey_name)
	geo_questions = survey.geo_questions()

	for question in geo_questions:
		#получить ответы
		answers = question.answers()

		print(type(answers[0]))
		#сформировать geojson файл
		geojson_str = serialize('geojson', answers, geometry_field=question.input_type)
			#cформировать файлы
		zip.writestr(question.name + '.geojson', geojson_str)

	#Windows bug fix
	for file in zip.filelist:
		file.create_system = 0

	zip.close()
	response = HttpResponse(content_type="application/zip")
	response["Content-Disposition"] = "attachment; filename={filename}.zip".format(filename=survey_name)

	in_memory.seek(0)
	response.write(in_memory.read())

	return response
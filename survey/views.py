from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from .models import SurveyHeader, SurveySession, SurveySection, Answer, Question, OptionChoice
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
import json
from zipfile import ZipFile
import pandas as pd

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
	start_section = survey.start_section()

	redirect_page = ("../" + survey_name + "/" + start_section.name) if start_section else survey.redirect_url
	
	return HttpResponseRedirect(redirect_page)
	
	#context = {'survey': survey, 'section': survey.start_section()}

	#return render(request, 'survey_header.html', context)


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

			if (result != []):
				if question.option_group is None:
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
										sub_question = Question.objects.get(Q(survey_section=section) & Q(code=key))
										sub_answer = Answer(survey_session=survey_session, question=sub_question, parent_answer_id = answer)
										if sub_question.option_group is None:
											if (sub_question.input_type == 'text' or sub_question.input_type == 'text_line') and value and value[0]:
												sub_answer.text = value[0]
											elif sub_question.input_type == 'number' and value and value[0]:
												sub_answer.numeric = float(value[0])
											else:
												pass
										else:
											if(sub_question.input_type == 'range') and value and value[0]:
												sub_answer.numeric = float(value[0])
											else:
												sub_answer.save()
												for result_answer in value:
													choice = OptionChoice.objects.get(Q(option_group=sub_question.option_group) & Q(code=result_answer))
													sub_answer.choice.add(choice)

										sub_answer.save()


					else:
						answer = Answer(survey_session=survey_session, question=question)

						if (question.input_type == "text" or question.input_type == "text_line"):
							answer.text = result
						elif question.input_type == "number":
							if result:
								answer.numeric = float(result)
						else:
							pass

						answer.save()

				else:
					answer = Answer(survey_session=survey_session, question=question)
					if  question.input_type == "range":
						answer.numeric = float(result[0])
					else:
						answer.save()
						for result_answer in result:
							if result_answer:
								try:
									choice = OptionChoice.objects.get(Q(option_group=question.option_group) & Q(code=result_answer))
									answer.choice.add(choice)
								except Exception as e:
									print(e)

						answer.save()

		next_page = ("../" + section.next_section.name) if section.next_section else survey.redirect_url
		return HttpResponseRedirect(next_page)

	else:
		form = SurveySectionAnswerForm(initial={}, section=section, question=None, survey_session_id=request.session['survey_session_id'])

		questions = section.questions();
	
		subquestions_forms = {}
		for question in questions:
			subquestions_forms[question.code] = SurveySectionAnswerForm(initial={}, section=section, question=question, survey_session_id=request.session['survey_session_id']).as_p().replace("/script", "\/script")
		


	return render(request, 'survey_section.html', {'form': form, 'subquestions_forms':subquestions_forms, 'survey':survey, 'section':section})

@login_required
def download_data(request, survey_name):
	in_memory = BytesIO()
	zip = ZipFile(in_memory, "a")

	survey = SurveyHeader.objects.get(name=survey_name)
	
	#обработка гео вопросов
	geo_questions = survey.geo_questions()	

	for question in geo_questions:
		
		layer_properties = {
			"survey": question.survey_section.survey_header.name,
			"survey_section": question.survey_section.name,
			"required": question.required,
		}

		#layer_str = geojson_template.format(layer_name = question.name, properties=layer_properties)

		#получить ответы
		features = []
		answers = question.answers()
		for answer in answers:
			#получить геометрию
			geo_type = question.input_type
			if geo_type == "polygon":
				coordinates =  [[[i[0],i[1]] for i in answer.polygon.coords[0]]]
				geometry_type = "Polygon"
			elif geo_type == "line":
				coordinates =  [[i[0],i[1]] for i in answer.line.coords]
				geometry_type = "LineString"
			elif geo_type == "point":
				coordinates =  [answer.point.coords[0], answer.point.coords[1]]
				geometry_type = "Point"

			#получить properties из subquestions
			subquestions = question.subQuestions()
			properties = {}
			subanswers = answer.subAnswers()
			result = ""
			for key in subanswers:
				input_type = key.input_type
				if (input_type == "text" or input_type == "text_line"):
					if subanswers[key]:
						answer = subanswers[key][0]
						result = answer.text
				elif input_type == "number" or input_type == "range":
					if subanswers[key]:
						answer = subanswers[key][0]
						result = answer.numeric
				elif input_type == "choice" or input_type == "rating":
					if subanswers[key]:
						answer = subanswers[key][0]
						result =answer.choice.all()[0].name
				elif input_type == "multichoice":
					if subanswers[key]:
						result = [a.name for a in subanswers[key][0].choice.all()]

				properties[key.name] = result

			properties["session"] = str(answer.survey_session)

			feature = {
				"type": "Feature",
				"properties": properties,
				"geometry":{
					"type": geometry_type,
					"coordinates": coordinates,
				}
			}

			features.append(feature)
		
		geojson_dict = {
			"type": "FeatureCollection", 
			"name": question.name,
			"crs": {"type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" }},
			"properties": layer_properties,
			"features": features,
		} 

		geojson_str = json.dumps(geojson_dict, ensure_ascii=False).encode('utf8')

		#сформировать geojson файл
		#geojson_str = serialize('geojson', answers, geometry_field=question.input_type)
		
		#cформировать файлы
		zip.writestr(question.name + '.geojson', geojson_str)

	#обработка обычных вопросов

	sessions = survey.sessions()

	properties_list = []
	for session in sessions:
		properties = {}
		answers = session.answers()
		result = ""
		for answer in answers:
			input_type = answer.question.input_type
			
			if (input_type == "text" or input_type == "text_line"):
				result = answer.text
			elif input_type == "number" or input_type == "range":
				result = answer.numeric
			elif input_type == "choice" or input_type == "rating":
				result = answer.choice.all()[0].name
			elif input_type == "multichoice":
				
				result = [c.name for c in answer.choice.all()]
			else:
				continue

			properties[answer.question.name] = result

		properties["session"] = str(session)
		properties["datetime"] = session.start_datetime
		properties_list.append(properties)

	zip.writestr(survey.name + '.csv', pd.DataFrame(properties_list).to_csv())


	#Windows bug fix
	for file in zip.filelist:
		file.create_system = 0

	zip.close()
	response = HttpResponse(content_type="application/zip")
	response["Content-Disposition"] = "attachment; filename={filename}.zip".format(filename=survey_name)

	in_memory.seek(0)
	response.write(in_memory.read())

	return response
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.utils import translation
from .models import SurveyHeader, SurveySession, SurveySection, Answer, Question, Story
from datetime import datetime
from django import forms
from django.views.generic import UpdateView
from .forms import SurveySectionAnswerForm
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.core.serializers import serialize
from django.db.models import Count
import geojson
from django.contrib.gis.geos import GEOSGeometry
import sys
from io import BytesIO
import json
from zipfile import ZipFile
import pandas as pd

from .serialization import (
    export_survey_to_zip,
    import_survey_from_zip,
    ImportError as SerializationImportError,
    ExportError,
    EXPORT_MODES,
)

def index(request):
	surveys = (
		SurveyHeader.objects
		.filter(visibility__in=['demo', 'public'])
		.select_related('organization')
		.annotate(session_count=Count('surveysession'))
		.order_by(
			models.Case(
				models.When(visibility='demo', then=0),
				models.When(is_archived=False, then=1),
				default=2,
				output_field=models.IntegerField(),
			)
		)
	)
	stories = Story.objects.filter(is_published=True).order_by('-published_date')
	return render(request, 'landing.html', {
		'surveys': surveys,
		'stories': stories,
	})

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


# ISO 639-1 language names in their native form
LANGUAGE_NAMES = {
	'en': 'English',
	'ru': 'Русский',
	'ky': 'Кыргызча',
	'uz': "O'zbekcha",
	'tg': 'Тоҷикӣ',
	'kk': 'Қазақша',
	'de': 'Deutsch',
	'fr': 'Français',
	'es': 'Español',
	'it': 'Italiano',
	'pt': 'Português',
	'zh': '中文',
	'ja': '日本語',
	'ko': '한국어',
	'ar': 'العربية',
	'hi': 'हिन्दी',
	'pl': 'Polski',
	'uk': 'Українська',
	'nl': 'Nederlands',
	'sv': 'Svenska',
	'fi': 'Suomi',
	'no': 'Norsk',
	'da': 'Dansk',
	'cs': 'Čeština',
	'tr': 'Türkçe',
	'he': 'עברית',
	'th': 'ไทย',
	'vi': 'Tiếng Việt',
	'az': 'Azərbaycanca',
	'ka': 'ქართული',
	'hy': 'Հայերdelays',
	'mn': 'Монгол',
}


def survey_language_select(request, survey_name):
	"""Display language selection screen for multilingual surveys."""
	survey = SurveyHeader.objects.get(name=survey_name)

	if not survey.is_multilingual():
		# Single-language survey - redirect directly to first section
		return redirect('survey', survey_name=survey_name)

	if request.method == 'POST':
		selected_language = request.POST.get('language')
		if selected_language and selected_language in survey.available_languages:
			# Activate Django i18n language
			translation.activate(selected_language)
			request.session['_language'] = selected_language

			# Create or update survey session with selected language
			if request.session.get('survey_session_id'):
				del request.session['survey_session_id']

			survey_session = SurveySession(survey=survey, language=selected_language)
			survey_session.save()
			request.session['survey_session_id'] = survey_session.id
			request.session['survey_language'] = selected_language

			# Redirect to first section
			start_section = survey.start_section()
			if start_section:
				return redirect('section', survey_name=survey_name, section_name=start_section.name)
			return redirect(survey.redirect_url)

	# Build language list with native names
	languages = []
	for lang_code in survey.available_languages:
		languages.append({
			'code': lang_code,
			'name': LANGUAGE_NAMES.get(lang_code, lang_code)
		})

	context = {
		'survey': survey,
		'languages': languages,
	}
	return render(request, 'survey_language_select.html', context)


def survey_header(request, survey_name):
	if request.session.get('survey_session_id'):
		del request.session['survey_session_id']
	if request.session.get('survey_language'):
		del request.session['survey_language']

	survey = SurveyHeader.objects.get(name=survey_name)

	# Redirect to language selection for multilingual surveys
	if survey.is_multilingual():
		return redirect('survey_language_select', survey_name=survey_name)

	start_section = survey.start_section()
	redirect_page = ("../" + survey_name + "/" + start_section.name) if start_section else survey.redirect_url

	return HttpResponseRedirect(redirect_page)
	
	#context = {'survey': survey, 'section': survey.start_section()}

	#return render(request, 'survey_header.html', context)


def survey_section(request, survey_name, section_name):

	survey = SurveyHeader.objects.get(name=survey_name)

	# For multilingual surveys, redirect to language selection if no language chosen
	if survey.is_multilingual() and not request.session.get('survey_language'):
		return redirect('survey_language_select', survey_name=survey_name)

	# Get selected language (None for single-language surveys)
	selected_language = request.session.get('survey_language')

	#если сессия на задана, то создать запись сессии
	if  not request.session.get('survey_session_id'):
		survey_session = SurveySession(survey=survey, language=selected_language)
		survey_session.save()
		request.session['survey_session_id'] = survey_session.id

	section = SurveySection.objects.get(Q(survey_header=survey) & Q(name=section_name))

	# Compute progress: current section index (1-based) and total sections
	section_current = 1
	s = section
	while s.prev_section:
		s = s.prev_section
		section_current += 1
	section_total = section_current
	s = section
	while s.next_section:
		s = s.next_section
		section_total += 1

	if request.method == 'POST':
		form = SurveySectionAnswerForm(initial=request.POST, section=section, question=None, survey_session_id=request.session['survey_session_id'], language=selected_language)

		#save data to answers
		section_questions = section.questions()
		survey_session = SurveySession.objects.get(pk=request.session['survey_session_id'])

		# Delete existing answers for this session and section before saving new ones
		section_question_ids = [q.id for q in section_questions]
		Answer.objects.filter(
			survey_session=survey_session,
			question_id__in=section_question_ids,
			parent_answer_id__isnull=True,
		).delete()

		for question in section_questions:
			result = request.POST.getlist(question.code)

			if (result != []):
				if not question.choices:
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
										if not sub_question.choices:
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
												sub_answer.selected_choices = [int(v) for v in value if v]
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
						answer.selected_choices = [int(r) for r in result if r]

					answer.save()

		if section.next_section:
			next_page = "../" + section.next_section.name
		elif survey.redirect_url == "#":
			next_page = reverse('survey_thanks', args=[survey_name])
		else:
			next_page = survey.redirect_url
		return HttpResponseRedirect(next_page)

	else:
		questions = section.questions()

		# Query existing answers for this session and section
		existing_answers = Answer.objects.filter(
			survey_session_id=request.session['survey_session_id'],
			question__in=questions,
			parent_answer_id__isnull=True,
		).select_related('question')

		# Build initial dict for scalar fields and geo GeoJSON for geo fields
		initial = {}
		existing_geo_answers = {}
		answers_by_question = {}
		for answer in existing_answers:
			q = answer.question
			answers_by_question.setdefault(q.code, []).append(answer)

		for question in questions:
			q_answers = answers_by_question.get(question.code, [])
			if not q_answers:
				continue

			if question.input_type in ('point', 'line', 'polygon'):
				# Build GeoJSON features for geo answers
				features = []
				for answer in q_answers:
					geometry = getattr(answer, question.input_type)
					if geometry is None:
						continue
					feature = {
						'type': 'Feature',
						'geometry': json.loads(geometry.geojson),
						'properties': {'question_id': question.code},
					}
					# Add sub-question values
					child_answers = Answer.objects.filter(parent_answer_id=answer).select_related('question')
					for child in child_answers:
						sub_q = child.question
						if child.text is not None:
							feature['properties'][sub_q.code] = [child.text]
						elif child.numeric is not None:
							feature['properties'][sub_q.code] = [str(child.numeric)]
						elif child.selected_choices:
							feature['properties'][sub_q.code] = [str(c) for c in child.selected_choices]
					features.append(feature)
				if features:
					existing_geo_answers[question.code] = features
			else:
				answer = q_answers[0]
				if question.input_type in ('text', 'text_line', 'datetime'):
					if answer.text is not None:
						initial[question.code] = answer.text
				elif question.input_type == 'number':
					if answer.numeric is not None:
						initial[question.code] = answer.numeric
				elif question.input_type in ('choice', 'rating'):
					if answer.selected_choices:
						initial[question.code] = str(answer.selected_choices[0])
					elif answer.numeric is not None:
						initial[question.code] = str(int(answer.numeric))
				elif question.input_type == 'multichoice':
					if answer.selected_choices:
						initial[question.code] = [str(c) for c in answer.selected_choices]
				elif question.input_type == 'range':
					if answer.numeric is not None:
						initial[question.code] = int(answer.numeric)

		form = SurveySectionAnswerForm(initial=initial, section=section, question=None, survey_session_id=request.session['survey_session_id'], language=selected_language)

		subquestions_forms = {}
		for question in questions:
			subquestions_forms[question.code] = SurveySectionAnswerForm(initial={}, section=section, question=question, survey_session_id=request.session['survey_session_id'], language=selected_language).as_p().replace("/script", "\/script")

		existing_geo_answers_json = json.dumps(existing_geo_answers)


	# Get translated section title and subheading for template
	section_title = section.get_translated_title(selected_language)
	section_subheading = section.get_translated_subheading(selected_language)

	return render(request, 'survey_section.html', {
		'form': form,
		'subquestions_forms': subquestions_forms,
		'survey': survey,
		'section': section,
		'section_title': section_title,
		'section_subheading': section_subheading,
		'selected_language': selected_language,
		'existing_geo_answers_json': existing_geo_answers_json,
		'section_current': section_current,
		'section_total': section_total,
	})

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
						names = answer.get_selected_choice_names()
						result = names[0] if names else ""
				elif input_type == "multichoice":
					if subanswers[key]:
						result = subanswers[key][0].get_selected_choice_names()

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
				names = answer.get_selected_choice_names()
				result = names[0] if names else ""
			elif input_type == "multichoice":
				result = answer.get_selected_choice_names()
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


@login_required
def export_survey(request, survey_name):
	"""Export survey to ZIP archive with specified mode."""
	mode = request.GET.get('mode', 'structure')

	if mode not in EXPORT_MODES:
		messages.error(request, f"Invalid export mode '{mode}'")
		return redirect('editor')

	try:
		survey = SurveyHeader.objects.get(name=survey_name)
	except SurveyHeader.DoesNotExist:
		messages.error(request, f"Survey '{survey_name}' not found")
		return redirect('editor')

	try:
		in_memory = BytesIO()
		warnings = export_survey_to_zip(survey, in_memory, mode)

		# Show warnings as messages
		for warning in warnings:
			messages.warning(request, warning)

		response = HttpResponse(content_type="application/zip")
		response["Content-Disposition"] = f"attachment; filename=survey_{survey_name}_{mode}.zip"

		in_memory.seek(0)
		response.write(in_memory.read())

		return response

	except ExportError as e:
		messages.error(request, str(e))
		return redirect('editor')


@login_required
def import_survey(request):
	"""Import survey from uploaded ZIP archive."""
	if request.method != 'POST':
		return redirect('editor')

	if 'file' not in request.FILES:
		messages.error(request, "No file uploaded")
		return redirect('editor')

	uploaded_file = request.FILES['file']

	try:
		survey, warnings = import_survey_from_zip(uploaded_file)

		# Show warnings
		for warning in warnings:
			messages.warning(request, warning)

		if survey:
			messages.success(request, f"Survey '{survey.name}' imported successfully")
		else:
			messages.success(request, "Data imported successfully")

	except SerializationImportError as e:
		messages.error(request, str(e))

	return redirect('editor')


def story_detail(request, slug):
	try:
		story = Story.objects.select_related('survey').get(slug=slug, is_published=True)
	except Story.DoesNotExist:
		raise Http404
	return render(request, 'story_detail.html', {'story': story})


@login_required
def delete_survey(request, survey_name):
	"""Delete a survey and all related data."""
	if request.method != 'POST':
		messages.error(request, "Invalid request method")
		return redirect('editor')

	try:
		survey = SurveyHeader.objects.get(name=survey_name)
		survey.delete()
		messages.success(request, f"Survey '{survey_name}' deleted successfully")
	except SurveyHeader.DoesNotExist:
		messages.error(request, f"Survey '{survey_name}' not found")

	return redirect('editor')


def survey_thanks(request, survey_name):
	survey = get_object_or_404(SurveyHeader, name=survey_name)
	lang = request.session.pop('survey_language', None)
	request.session.pop('survey_session_id', None)

	thanks_html = resolve_thanks_html(survey.thanks_html, lang)

	return render(request, 'survey_thanks.html', {
		'survey_name': survey_name,
		'thanks_html': thanks_html,
		'lang': lang or 'en',
	})


def resolve_thanks_html(thanks_html, lang):
	"""Resolve thanks_html content by language.

	Accepts a dict keyed by language code or a plain string.
	Fallback chain: requested lang → "en" → first available → None.
	"""
	if not thanks_html:
		return None
	if isinstance(thanks_html, str):
		return thanks_html
	if isinstance(thanks_html, dict):
		if lang and lang in thanks_html:
			return thanks_html[lang]
		if 'en' in thanks_html:
			return thanks_html['en']
		if thanks_html:
			return next(iter(thanks_html.values()))
	return None
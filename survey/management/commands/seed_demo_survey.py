"""Install the "Cycling in Copenhagen" demo survey (change copenhagen-demo).

    python manage.py seed_demo_survey --org mapsurvey
    python manage.py seed_demo_survey --org mapsurvey --replace
    python manage.py seed_demo_survey --org mapsurvey --remove-samples

The structure lives in survey/demo_data/copenhagen_cycling/ and goes through the same
ZIP import creators use. What an archive cannot carry is added here afterwards: sample
responses (every session tagged `sample`), the shared-map marks materialised from them,
and a published public results page. No network access; the data files are built once
by scripts/build_copenhagen_demo.py and committed.

Questions are found by section name + question name after import, never by the codes in
survey.json: an import into a database that already holds those codes remaps them.
"""
import io
import json
import zipfile
from datetime import timedelta
from pathlib import Path

from django.contrib.gis.geos import LineString, Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from survey import layers as layer_utils
from survey.models import (
    Answer, Organization, PublicResultsPage, Question, SurveyHeader, SurveyMapLayer, SurveySession,
)
from survey.public_results import bump_page_version, scaffold_page
from survey.question_types import THUMBS_DOWN, THUMBS_UP
from survey.serialization import import_survey_from_zip
from survey.trash import purge_survey

DATA_DIR = Path(__file__).resolve().parents[2] / 'demo_data' / 'copenhagen_cycling'
SAMPLE_TAG = 'sample'
RESULTS_SLUG = 'copenhagen-cycling-demo'
RESULTS_INTRO = {
    'title': {'en': 'Cycling in Copenhagen: what people told us'},
    'body': {'en': 'This is the public results page of a Mapsurvey demo, not a survey run by the City '
                   'of Copenhagen. Most answers here are sample answers, added so the page shows what a '
                   'creator can publish; answers from visitors who take the demo join them.'},
}


def survey_name():
    return json.loads((DATA_DIR / 'survey.json').read_text())['survey']['name']


def build_archive():
    """The demo directory as an in-memory ZIP, minus the files only the command reads."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(DATA_DIR.rglob('*')):
            if path.is_file() and path.name != 'samples.json':
                zf.write(path, path.relative_to(DATA_DIR).as_posix())
    buf.seek(0)
    return buf


class Command(BaseCommand):
    help = 'Install the Cycling in Copenhagen demo survey with tagged sample responses.'

    def add_arguments(self, parser):
        parser.add_argument('--org', required=True, help='Slug of the organisation that owns the demo.')
        parser.add_argument('--replace', action='store_true',
                            help='Delete an existing demo (with its responses and results page) first.')
        parser.add_argument('--remove-samples', action='store_true',
                            help='Only delete the sessions tagged "sample" from the existing demo.')

    def handle(self, *args, **opts):
        org = Organization.objects.filter(slug=opts['org']).first()
        if org is None:
            raise CommandError(f"No organisation with slug '{opts['org']}'.")
        existing = SurveyHeader.objects.filter(organization=org, name=survey_name(), is_canonical=True).first()

        if opts['remove_samples']:
            if existing is None:
                raise CommandError('No demo survey in this organisation.')
            removed = remove_samples(existing)
            self.stdout.write(f'Removed {removed} sample sessions.')
            return

        if existing is not None:
            if not opts['replace']:
                self.stdout.write(self.style.WARNING(
                    f'The demo already exists ({existing.uuid}); nothing changed. Use --replace to reinstall.'))
                return
            purge_survey(existing)
            self.stdout.write(f'Deleted the previous demo {existing.uuid}.')

        with transaction.atomic():
            survey, warnings = import_survey_from_zip(build_archive(), organization=org)
            for line in warnings:
                self.stdout.write(self.style.WARNING(f'  import: {line}'))
            survey.status = 'published'
            survey.save(update_fields=['status'])
            counts = seed_samples(survey, json.loads((DATA_DIR / 'samples.json').read_text()))
            page = publish_results_page(survey)

        self.stdout.write(self.style.SUCCESS(
            f"Demo installed: {counts['sessions']} sample sessions, {counts['marks']} shared marks."))
        self.stdout.write(f"  survey:  {reverse('survey', kwargs={'survey_slug': str(survey.uuid)})}")
        self.stdout.write(f"  results: /r/{page.slug}/")
        self.stdout.write(f'  set DEMO_SURVEY_URL to <site>/surveys/{survey.uuid}')


class DemoQuestions:
    """The demo's questions, found by section + question name (codes may be remapped)."""

    def __init__(self, survey):
        rows = Question.objects.filter(survey_section__survey_header=survey).select_related('survey_section')
        self._by = {(q.survey_section.name, q.parent_question_id_id, q.name): q for q in rows}
        self.survey = survey

    def top(self, section, name):
        return self._by[(section, None, name)]

    def sub(self, parent, name):
        return self._by[(parent.survey_section.name, parent.pk, name)]


def seed_samples(survey, data):
    q = DemoQuestions(survey)
    freq = q.top('adapt', 'How often do you cycle in Copenhagen?')
    use = q.top('adapt', 'What do you use your bike for?')
    barriers = q.top('adapt', 'What keeps you off the bike?')
    safe = q.top('adapt', 'How safe do you feel cycling in the city centre?')
    bridges = q.top('bridges', 'Rate the bridges you have crossed')
    bridge_thumb = q.sub(bridges, 'Is this bridge good to cycle across?')
    bridge_note = q.sub(bridges, 'What would make it better?')
    spot = q.top('spot', 'Mark a spot where cycling feels unsafe')
    spot_why = q.sub(spot, 'What is the problem?')
    spot_note = q.sub(spot, 'Anything else?')
    route = q.top('route', 'Draw the route you ride most often')
    route_rate = q.sub(route, 'How pleasant is this route?')
    others = q.top('others', 'Unsafe spots marked by others')
    other_thumb = q.sub(others, 'Do you agree this spot is unsafe?')
    other_note = q.sub(others, 'Add a comment')
    bridge_objects = {o.key: o for o in bridges.layer.items.all()}

    now = timezone.now()
    sessions = []
    for row in data['sessions']:
        started = now - timedelta(days=row['days_ago'])
        session = SurveySession.objects.create(
            survey=survey, start_datetime=started, end_datetime=started + timedelta(minutes=3),
            last_activity_at=started + timedelta(minutes=3), language='en', tags=[SAMPLE_TAG],
            opened_by_kind=SurveySession.OPENED_BY_EXTERNAL,
        )
        sessions.append(session)
        answer = lambda question, **kw: Answer.objects.create(survey_session=session, question=question, **kw)
        answer(freq, selected_choices=[row['freq']])
        if row['use']:
            answer(use, selected_choices=row['use'])
        if row['barriers']:
            answer(barriers, selected_choices=row['barriers'])
        answer(safe, selected_choices=[row['safe']])
        for item in row['bridges']:
            obj = bridge_objects[item['key']]
            answer(bridge_thumb, layer_object=obj, selected_choices=[THUMBS_UP if item['up'] else THUMBS_DOWN])
            if item['note']:
                answer(bridge_note, layer_object=obj, text=item['note'])
        for mark in row['spots']:
            parent = answer(spot, point=Point(*mark['lonlat'], srid=4326))
            answer(spot_why, parent_answer_id=parent, selected_choices=[mark['why']])
            if mark['note']:
                answer(spot_note, parent_answer_id=parent, text=mark['note'])
        if row['route']:
            parent = answer(route, line=LineString(row['route']['coords'], srid=4326))
            answer(route_rate, parent_answer_id=parent, selected_choices=[row['route']['rate']])

    # The shared map: the same materialisation the editor runs when a layer is added
    # after collection started, so sample marks get the keys real ones get.
    shared = others.layer
    marks = layer_utils.backfill_question_layer(shared)
    objects = {o.key: o for o in shared.items.all()}
    for session, row in zip(sessions, data['sessions']):
        for reaction in row['reactions']:
            key = layer_utils.QUESTION_LAYER_KEY.format(session=sessions[reaction['session']].pk,
                                                        index=reaction['spot'] + 1)
            obj = objects.get(key)
            if obj is None:
                continue
            Answer.objects.create(survey_session=session, question=other_thumb, layer_object=obj,
                                  selected_choices=[THUMBS_UP if reaction['up'] else THUMBS_DOWN])
            if reaction['note']:
                Answer.objects.create(survey_session=session, question=other_note, layer_object=obj,
                                      text=reaction['note'])
    return {'sessions': len(sessions), 'marks': marks}


def publish_results_page(survey):
    page = scaffold_page(survey)
    if not PublicResultsPage.objects.filter(slug=RESULTS_SLUG).exclude(pk=page.pk).exists():
        page.slug = RESULTS_SLUG
    page.is_published = True
    page.visibility = 'unlisted'
    page.intro = RESULTS_INTRO
    page.save()
    bump_page_version(page)
    return page


def remove_samples(survey):
    sessions = SurveySession.objects.filter(survey=survey, tags__contains=[SAMPLE_TAG])
    count = sessions.count()
    with transaction.atomic():
        sessions.delete()
        for layer in SurveyMapLayer.objects.filter(survey=survey, source='question'):
            layer_utils.rebuild_layer(layer)
    return count

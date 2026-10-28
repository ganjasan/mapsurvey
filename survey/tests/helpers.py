"""Shared fixtures and helpers for the survey test modules (moved from survey/tests.py, #273)."""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, LineString
from django.urls import reverse
from django.utils import timezone
from io import BytesIO
from unittest import mock
from unittest.mock import patch
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator, PublicResultsPage, PublicResultsBlock
import os
import tempfile
import datetime
from survey import comments as _cm
from django.core import mail as _cs_mail
from survey.content_screening import ScreenInput as _ScreenInput



def _make_org(name='TestOrg'):
    """Helper to create an organization for tests."""
    return Organization.objects.create(name=name, slug=name.lower().replace(' ', '-'))


def _eager_import():
    """Run the ZIP import job inline. The view only enqueues a Celery task and
    the suite has no broker, so `.delay` becomes the task itself (the AI draft
    tests patch their task the same way)."""
    from unittest.mock import patch
    from survey.tasks import run_survey_import
    return patch('survey.views.run_survey_import.delay', side_effect=lambda job_id: run_survey_import(job_id))


def _zip_text(response):
    """Concatenated text of every file in a download_data ZIP response."""
    chunks = []
    with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
        for name in zf.namelist():
            chunks.append(zf.read(name).decode('utf-8', errors='replace'))
    return '\n'.join(chunks)


def _make_survey_with_section(org, name, owner=None):
    survey = SurveyHeader.objects.create(
        name=name, visibility='private', organization=org,
        created_by=owner,
    )
    section = SurveySection.objects.create(
        survey_header=survey, name='sec_a', title='Section A', code='SA', is_head=True,
    )
    return survey, section


def _user_at(username, when, **kwargs):
    """Create a user whose date_joined is pinned to `when` (tz consistent)."""
    u = User.objects.create_user(username=username, password="x", **kwargs)
    u.date_joined = when
    u.save(update_fields=["date_joined"])
    return u


def _u(username, joined, email="x@gmail.com"):
    u = User.objects.create_user(username=username, password="x", email=email)
    u.date_joined = joined
    u.save(update_fields=["date_joined"])
    return u


def _activation_key(username):
    """Sign an activation key exactly as django-registration does."""
    from django.core import signing
    from django_registration.backends.activation import REGISTRATION_SALT

    return signing.dumps(obj=username, salt=REGISTRATION_SALT)


# Rate limiting is counted in the cache. The configured backend is Redis with
# IGNORE_EXCEPTIONS, so when Redis is absent every counter silently no-ops and
# limits never fire. Pin an in-process cache for limit tests instead.
_LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "activation-funnel-test",
    }
}


class _InlineThread:
    """Stand-in for threading.Thread that runs its target synchronously.

    Activation mail is dispatched from a background thread so the response
    time is the same whether or not mail was sent — that uniformity is what
    stops the resend endpoint leaking account existence through timing. The
    side effect is that mail.outbox assertions race the thread. Running the
    target inline makes them deterministic without altering the code path
    under test.
    """

    def __init__(self, target=None, kwargs=None, daemon=None, **_ignored):
        self._target = target
        self._kwargs = kwargs or {}

    def start(self):
        self._target(**self._kwargs)


# ─── AI survey draft generation ──────────────────────────────────────────────

def _ai_question(name_en, input_type='text', languages=('en',), choices=None,
                 sub_questions=None, required=False, color=None, icon=None):
    """Build one question in the model-output shape (localized dicts, no codes)."""
    from survey.question_types import GEO_TYPES as _GEO
    is_geo = input_type in _GEO
    question = {
        'name': {lang: f'{name_en} [{lang}]' for lang in languages},
        'subtext': {lang: '' for lang in languages},
        'input_type': input_type,
        'required': required,
        'choices': choices or [],
        'sub_questions': sub_questions or [],
        # Top-level style fields; geo questions must carry real values.
        'color': color if color is not None else ('#E8590C' if is_geo else ''),
        'icon': icon if icon is not None else ('map-marker-alt' if input_type == 'point' else 'none'),
    }
    return question


def _ai_choice(code, label, languages=('en',)):
    return {'code': code, 'name': {lang: f'{label} [{lang}]' for lang in languages}}


def _ai_blob(languages=('en',)):
    """A well-formed draft: 2 sections, one point question with a sub-question."""
    return {
        'sections': [
            {
                'title': {lang: f'About you [{lang}]' for lang in languages},
                'subheading': {lang: '' for lang in languages},
                'questions': [
                    _ai_question('How do you travel?', 'choice', languages, choices=[
                        _ai_choice(1, 'On foot', languages),
                        _ai_choice(2, 'By bike', languages),
                    ]),
                ],
            },
            {
                'title': {lang: f'Problem spots [{lang}]' for lang in languages},
                'subheading': {lang: '' for lang in languages},
                'questions': [
                    _ai_question(
                        'Mark the worst spot', 'point', languages, required=True,
                        sub_questions=[
                            _ai_question('What is wrong there?', 'text', languages),
                        ],
                    ),
                    _ai_question('How severe is it?', 'rating', languages, choices=[
                        _ai_choice(1, 'Minor', languages),
                        _ai_choice(5, 'Severe', languages),
                    ]),
                ],
            },
        ],
    }


class _FakeProvider:
    """Stands in for a real model: returns queued blobs, counts calls."""

    def __init__(self, blobs, error=None, usages=None):
        self._blobs = list(blobs)
        self._error = error
        # Per-call usage overrides, consumed in order. Without them every call
        # reports the same numbers, which cannot distinguish a summed attempt
        # set from a single call -- the exact thing the accounting must prove.
        self._usages = list(usages) if usages else None
        self.calls = []

    def complete_structured(self, *, system, user, schema, max_tokens=64000, on_progress=None):
        from survey.ai.client import LLMUsage

        self.calls.append(user)
        if self._error is not None:
            raise self._error
        blob = self._blobs.pop(0)
        overrides = self._usages.pop(0) if self._usages else {}
        usage = LLMUsage(**dict(
            {'provider': 'fake', 'model': 'fake-model',
             'input_tokens': 100, 'output_tokens': 200, 'latency_ms': 1234},
            **overrides
        ))
        return blob, usage


class _ProgressingProvider(_FakeProvider):
    """A fake that reports draft progress before handing back its blob.

    Stands in for a streaming provider without a stream: the orchestrator only
    ever sees the callback being invoked, so a scripted sequence of counts
    exercises the same wiring an SSE response would.
    """

    def __init__(self, blobs, steps, progress_on_first_only=False, **kwargs):
        super().__init__(blobs, **kwargs)
        self._steps = list(steps)
        self._progress_on_first_only = progress_on_first_only
        self._call = 0

    def complete_structured(self, *, system, user, schema, max_tokens=64000, on_progress=None):
        self._call += 1
        if on_progress is not None and not (self._progress_on_first_only and self._call > 1):
            for sections, questions in self._steps:
                on_progress(sections, questions)
        return super().complete_structured(
            system=system, user=user, schema=schema, max_tokens=max_tokens,
        )


class _FlakyProvider(_FakeProvider):
    """Fails a scripted number of calls before behaving, like a provider under load."""

    def __init__(self, blobs, error, failures, **kwargs):
        super().__init__(blobs, **kwargs)
        self._error = None  # the base class would raise it on every call
        self._flaky_error = error
        self._failures = failures
        self.attempts_made = 0

    def complete_structured(self, *, system, user, schema, max_tokens=64000, on_progress=None):
        self.attempts_made += 1
        if self.attempts_made <= self._failures:
            raise self._flaky_error
        return super().complete_structured(
            system=system, user=user, schema=schema, max_tokens=max_tokens,
        )


class _AIGenerationFixture:
    """Fixtures and the run helper shared by the orchestrator test classes.

    A mixin rather than a base TestCase: subclassing a TestCase would re-run
    every inherited test method in each child, which doubles the suite's slowest
    AI cases for no coverage.
    """

    def setUp(self):
        self.org = _make_org('AIGenOrg')
        self.user = User.objects.create_user('aigenuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

    def _brief(self):
        from survey.ai.generation import SurveyBrief

        return SurveyBrief(
            name='traffic_survey', goal='Where is traffic worst',
            audience='Residents', map_target='Congestion spots',
            use_case='urban_planning',
        )

    def _run(self, provider, languages=('en',)):
        from survey.ai.generation import generate_survey_draft, start_generation
        from survey.ai.materialize import header_overrides_from_form

        brief = self._brief()
        event = start_generation(self.user, self.org, brief, list(languages))
        overrides = header_overrides_from_form(
            name=brief.name, languages=list(languages),
            map_lat='52.52', map_lng='13.405', map_zoom='12', default_basemap='streets',
        )
        with patch('survey.ai.generation.client.get_provider', return_value=provider):
            generate_survey_draft(event, brief, list(languages), overrides)
        event.refresh_from_db()
        return event


# =============================================================================
# Reference overlay layers (openspec: reference-overlay-layers)
# =============================================================================

def _zones_geojson(count=3, projected=False):
    """A small FeatureCollection shaped like a real zone file."""
    features = []
    for i in range(count):
        lng = (2000000 + i) if projected else (-88.10 + i * 0.01)
        lat = (5000000 + i) if projected else (38.72 + i * 0.01)
        features.append({
            "type": "Feature",
            "properties": {"name": f"Area {i + 1}", "zone_id": i + 1},
            "geometry": {"type": "Polygon", "coordinates": [[
                [lng, lat], [lng + 0.004, lat], [lng + 0.004, lat + 0.004], [lng, lat + 0.004], [lng, lat],
            ]]},
        })
    return json.dumps({"type": "FeatureCollection", "features": features})


def _validated_geojson_text(raw):
    """(FeatureCollection text, count, property names) the way pre-objects fixtures
    stored a layer: the validated parse re-serialised. Production never stores
    this text any more (rebuild_layer derives it from objects); a handful of
    fixtures still seed the column directly."""
    from survey.layers import validate_layer_upload
    features, props, _z = validate_layer_upload(raw)
    text = json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, separators=(',', ':'))
    return text, len(features), props


# ─── overlay-features: layer objects ────────────────────────────────────────

def _objects_layer(survey, name="Zones", geojson_text=None, **layer_fields):
    """A layer populated the way the editor and ZIP import populate it: objects
    first, derived GeoJSON second."""
    from survey.models import SurveyMapLayer
    from survey.layers import validate_layer_upload, objects_from_features, rebuild_layer
    features, _props, _z = validate_layer_upload((geojson_text or _zones_geojson()).encode())
    layer = SurveyMapLayer.objects.create(survey=survey, name=name, geojson='', **layer_fields)
    objects_from_features(layer, features)
    rebuild_layer(layer)
    return layer


# ═══════════════════════════════════════════════════════════════════════════
# Shared map — layers sourced from respondents' answers (change respondent-shared-map)
# ═══════════════════════════════════════════════════════════════════════════

def _shared_map_survey(name="shared_map_survey"):
    """A published survey with a point question Q1 (+ text sub-question WHY),
    a `question` layer reading Q1 labelled by WHY, and an Objects-on-the-map
    question OBJ bound to it with 👍/👎 (VOTE) and comment (CMT) sub-questions."""
    from survey.models import SurveyMapLayer
    org = Organization.objects.create(name=f"{name} org")
    survey = SurveyHeader.objects.create(name=name, organization=org, redirect_url="/thanks/", status='published')
    section = SurveySection.objects.create(survey_header=survey, name="s1", title="S1", code="S1", is_head=True)
    q1 = Question.objects.create(survey_section=section, code="Q1", name="Where?", input_type="point", order_number=1)
    why = Question.objects.create(survey_section=section, code="WHY", name="Why here?", input_type="text",
                                  parent_question_id=q1, order_number=1)
    layer = SurveyMapLayer.objects.create(survey=survey, name="Marks: Where?", geojson='{"type":"FeatureCollection","features":[]}',
                                          source='question', source_question_code='Q1', label_field='WHY')
    obj = Question.objects.create(survey_section=section, code="OBJ", name="Marks by others", input_type="layer_objects",
                                  layer=layer, order_number=2)
    vote = Question.objects.create(survey_section=section, code="VOTE", name="Support?", input_type="thumbs",
                                   parent_question_id=obj, order_number=1, choices=[{"code": 1, "name": "up"}, {"code": 0, "name": "down"}],
                                   share_with_respondents=True)
    cmt = Question.objects.create(survey_section=section, code="CMT", name="Comment", input_type="text",
                                  parent_question_id=obj, order_number=2)
    return {'survey': survey, 'section': section, 'q1': q1, 'why': why, 'layer': layer,
            'obj': obj, 'vote': vote, 'cmt': cmt}


def _mark(session, q1, lng, lat, why=None):
    """A stored point answer with an optional WHY sub-answer, as the section POST stores them."""
    a = Answer.objects.create(survey_session=session, question=q1, point=Point(lng, lat))
    if why is not None:
        Answer.objects.create(survey_session=session, question=Question.objects.get(code='WHY', survey_section=q1.survey_section),
                              parent_answer_id=a, text=why)
    return a


def _react(session, obj_question, layer_object, up=None, comment=None):
    from survey.models import Question as Q_
    if up is not None:
        Answer.objects.create(survey_session=session, question=Q_.objects.get(code='VOTE', parent_question_id=obj_question),
                              layer_object=layer_object, selected_choices=[1 if up else 0])
    if comment is not None:
        Answer.objects.create(survey_session=session, question=Q_.objects.get(code='CMT', parent_question_id=obj_question),
                              layer_object=layer_object, text=comment)


# ═══════════════════════════════════════════════════════════════════════════
# Layer style — base + one rule by attribute (change layer-style)
# ═══════════════════════════════════════════════════════════════════════════

def _styled_layer(survey, name="Segments", n=8, **fields):
    """A layer of n line objects with priority_class (High/Medium/Low, one 'Odd')
    and priority_score properties, as an import would leave them."""
    from survey.models import SurveyMapLayer, LayerObject
    from survey.layers import rebuild_layer
    from django.contrib.gis.geos import LineString
    layer = SurveyMapLayer.objects.create(survey=survey, name=name, geojson='', **fields)
    classes = ['High', 'Medium', 'Low', 'High', 'Medium', 'Low', 'High', 'Odd']
    for i in range(n):
        LayerObject.objects.create(layer=layer, key=f'seg-{i}', title=f'Segment {i}', position=i,
                                   geometry=LineString((i, 0), (i, 1)),
                                   properties={'priority_class': classes[i % len(classes)], 'priority_score': 10 * i + 3})
    rebuild_layer(layer)
    return layer


class _CommentFixture(TestCase):
    """Org with an owner, a viewer, an editor (via SurveyCollaborator) and an
    outsider from another org; one survey with two sections, a question per
    section, one session and one public-results block."""

    def setUp(self):
        self.org = Organization.objects.create(name="Comment Org")
        self.other_org = Organization.objects.create(name="Other Org")
        self.owner = User.objects.create_user(username='cmowner', password='pw12345678', email='owner@example.com', first_name='Artem', last_name='K')
        self.viewer = User.objects.create_user(username='cmviewer', password='pw12345678', email='viewer@example.com', first_name='Kelsie', last_name='S')
        self.editor = User.objects.create_user(username='cmeditor', password='pw12345678', email='editor@example.com')
        self.outsider = User.objects.create_user(username='cmoutsider', password='pw12345678', email='out@example.com')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        Membership.objects.create(user=self.outsider, organization=self.other_org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="cm_survey", organization=self.org, redirect_url="/thanks/", created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.s1 = SurveySection.objects.create(survey_header=self.survey, name="intro", title="Intro", code="S1", is_head=True)
        self.s2 = SurveySection.objects.create(survey_header=self.survey, name="count", title="Count", code="S2")
        self.s1.next_section = self.s2
        self.s1.save()
        self.q1 = Question.objects.create(survey_section=self.s1, code="Q_1", order_number=1, name="Which area?", input_type="text")
        self.q2 = Question.objects.create(survey_section=self.s2, code="Q_2", order_number=1, name="White squirrel", input_type="point")
        self.session = SurveySession.objects.create(survey=self.survey)
        self.page = PublicResultsPage.objects.create(survey=self.survey, slug='cm-results')
        self.block = PublicResultsBlock.objects.create(page=self.page, block_type='map', question=self.q2, order=0)
        self.client.login(username='cmowner', password='pw12345678')

    def _u(self, name, **kw):
        kw.setdefault('survey_uuid', self.survey.uuid)
        return reverse(name, kwargs=kw)

    def _open(self, kind, key, body='hello', actor=None, mentions=()):
        thread, comment = _cm.open_thread(self.survey, actor or self.owner, kind, key, body, mentions)
        return thread, comment


_DEMO_MEDIA = tempfile.mkdtemp(prefix='demo-media-')


# ═══════════════════════════════════════════════════════════════════════════
# In-app changelog (change in-app-changelog, issue #227)
# ═══════════════════════════════════════════════════════════════════════════

def _changelog_dir(files):
    """A temporary entries directory with the given {filename: text}."""
    import tempfile as _tempfile
    directory = _tempfile.mkdtemp(prefix='changelog-')
    for name, text in files.items():
        with open(os.path.join(directory, name), 'w', encoding='utf-8') as fh:
            fh.write(text)
    return directory


_ENTRY_A = """---
title: Export as Excel
kind: new
---
<p>Five formats in the Export dialog.</p>
"""
_ENTRY_B = """---
title: Empty sessions are now hidden
kind: new
link: editor
image: favicon-32x32.png
---
<p>Responses leave out sessions where nobody answered.</p>
<p><strong>Why.</strong> They outnumbered real responses.</p>
"""
_ENTRY_FIX = """---
title: Geo answer edit no longer fails
kind: fixed
---
<p>It saves again.</p>
"""
_HERO = """---
title: Edit these surveys from your assistant
kind: new
tier: hero
art: agent
eyebrow: Your surveys, from your assistant
link: editor_survey_start_agent
link_query: from=dashboard
cta_label: Connect your assistant
help: mcp
chips: Summarise {survey}|Add a question to {survey}|Plain chip
show_if: has_surveys,no_mcp_connection
note_if: free_plan
note: Part of Pro
---
<p>Connect once.</p>
"""


def _dated(days_ago):
    """An entry id date `days_ago` days before today, for heroes whose lifetime
    is measured against the clock."""
    import datetime
    from django.utils import timezone
    return (timezone.localdate() - datetime.timedelta(days=days_ago)).isoformat()


class _ChangelogDirMixin:
    """Point the loader at a temporary directory for the test's lifetime."""

    def use_entries(self, files):
        from survey import changelog
        directory = _changelog_dir(files)
        patcher = mock.patch.object(changelog, 'ENTRIES_DIR', directory)
        patcher.start()
        self.addCleanup(patcher.stop)
        changelog.clear_cache()
        self.addCleanup(changelog.clear_cache)
        return directory


# ─────────────────────────────────────────────────────────────────────────────
# Empty sessions hidden on Responses and left out of exports
# (change hide-empty-sessions, issue #226, spec responses-empty-sessions)
# ─────────────────────────────────────────────────────────────────────────────

class _EmptySessionFixture(TestCase):
    """A survey with a text, a number and a point question (+ a sub-question)."""

    def setUp(self):
        self.org = _make_org('EmptySessOrg')
        self.owner = User.objects.create_user('emptysessowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='emptysessowner', password='pass')
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        self.survey = SurveyHeader.objects.create(
            name='empty_sess_survey', organization=self.org, created_by=self.owner,
            status='published', redirect_url='/thanks/',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='ES_T', input_type='text', order_number=1,
        )
        self.q_num = Question.objects.create(
            survey_section=self.section, name='Count', code='ES_N', input_type='number', order_number=2,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Where', code='ES_P', input_type='point', order_number=3,
        )
        self.q_sub = Question.objects.create(
            survey_section=self.section, name='Why', code='ES_P_W', input_type='text',
            parent_question_id=self.q_point, order_number=1,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'
        self.table_url = f'/editor/surveys/{self.survey.uuid}/analytics/table/'
        self._clock = timezone.now() - timezone.timedelta(days=2)

    def _session(self, answered=True, **kwargs):
        self._clock += timezone.timedelta(minutes=1)
        kwargs.setdefault('start_datetime', self._clock)
        sess = SurveySession.objects.create(survey=self.survey, **kwargs)
        if answered:
            Answer.objects.create(survey_session=sess, question=self.q_text, text='hello')
        return sess

_XFINITY_SUBHEADING = (
    '<p style="text-align:center"><strong>XFINITY</strong></p>'
    "<p style=\"text-align:center\">You're almost set! Access your Everymail email securely. "
    'Manage communications to your account from anywhere seamlessly.</p>'
    '<p style="text-align:center"><strong><a href="https://go.xaply.in/fp5qs" target="_blank" '
    'rel="noopener noreferrer">CLICK HERE TO PROCEED</a></strong></p>'
    + '<p style="text-align:center"><br></p>' * 74
)
_TRACKER_URL = ('https://sender10.zohoinsights.com/ck1/2d6f.327230a/52aab750-89e2-11f1-a2db-525400d4bb1c/'
                '0a29489b5ad81b76b5b8b74af2d72eca13465dd1/2?e=EmhJ3GkUtbm')


def _cs_input(texts, redirect='', questions=1, age_hours=0.03, domain='gmail.com'):
    return _ScreenInput(texts=[('t', t) for t in texts], redirect_url=redirect,
                        question_count=questions, account_age_hours=age_hours, email_domain=domain)


def _eager_notice():
    """Run the review notice inline: `.delay` becomes the task (no broker in the suite)."""
    from survey.tasks import send_abuse_review_notice
    return patch('survey.tasks.send_abuse_review_notice.delay',
                 side_effect=lambda review_id: send_abuse_review_notice(review_id))


class _ContentScreeningBase(TestCase):
    def setUp(self):
        self.org = _make_org('ScreenOrg')
        self.owner = User.objects.create_user(username='screen_owner', password='pass', email='owner@example.org')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='screen_test', organization=self.org, created_by=self.owner)
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True, title='Section 1',
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q_SCR1', name='Where?', input_type='text',
        )
        self.client.login(username='screen_owner', password='pass')
        _cs_mail.outbox = []

    def _make_lure(self):
        self.section.subheading = _XFINITY_SUBHEADING
        self.section.save(update_fields=['subheading'])
        self.question.name = 'XFINITY'
        self.question.save(update_fields=['name'])

    def _transition(self, status='published'):
        return self.client.post(f'/editor/surveys/{self.survey.uuid}/transition/',
                                {'status': status, 'ack_translation_gaps': 'true'}, HTTP_HX_REQUEST='true')

    def _publish(self):
        with _eager_notice():
            response = self._transition('published')
        self.survey.refresh_from_db()
        return response

    def _anon(self):
        return Client()


class _EmbedSurveyMixin:
    """A published two-section text survey, the shape the Share page embeds."""

    def _make_embed_survey(self, status='published', suffix='', **kwargs):
        survey = SurveyHeader.objects.create(
            name=f'embed_{status}{suffix}', organization=self.org, created_by=self.owner,
            status=status, **kwargs,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=survey, role='owner')
        s1 = SurveySection.objects.create(survey_header=survey, name='sec1', title='One', code='S1', is_head=True)
        s2 = SurveySection.objects.create(survey_header=survey, name='sec2', title='Two', code='S2')
        s1.next_section = s2
        s1.save()
        s2.prev_section = s1
        s2.save()
        Question.objects.create(survey_section=s1, code='Q1', order_number=1, name='Colour', input_type='text')
        Question.objects.create(survey_section=s2, code='Q2', order_number=1, name='City', input_type='text')
        return survey

    def setUp(self):
        self.org = _make_org('EmbedOrg')
        self.owner = User.objects.create_user(username='embed_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')


# ═══════════════════════════════════════════════════════════════════════════
# Pop-up visibility rules — sub-questions ruled by an earlier choice sub-question
# of the same pop-up (openspec: subquestion-visibility-rules, #338)
# ═══════════════════════════════════════════════════════════════════════════

def _popup_fixture(survey, section, code_prefix="PV", with_rules=True):
    """A point question whose pop-up asks "Type of place" (Park=1, School=2)
    and has one follow-up per type plus an unconditional comment."""
    point = Question.objects.create(
        survey_section=section, code=f"{code_prefix}_PT", order_number=1, name="Place",
        input_type="point")
    kind = Question.objects.create(
        survey_section=section, code=f"{code_prefix}_KIND", order_number=1, name="Type of place",
        input_type="choice", parent_question_id=point,
        choices=[{"code": 1, "name": "Park"}, {"code": 2, "name": "School"}])
    park = Question.objects.create(
        survey_section=section, code=f"{code_prefix}_PARK", order_number=2, name="Park follow-up",
        input_type="text_line", parent_question_id=point,
        visibility_rule={"question_code": kind.code, "choice_codes": [1]} if with_rules else None)
    school = Question.objects.create(
        survey_section=section, code=f"{code_prefix}_SCHOOL", order_number=3, name="School follow-up",
        input_type="text_line", parent_question_id=point,
        visibility_rule={"question_code": kind.code, "choice_codes": [2]} if with_rules else None)
    comment = Question.objects.create(
        survey_section=section, code=f"{code_prefix}_NOTE", order_number=4, name="Comment",
        input_type="text", parent_question_id=point)
    return {'point': point, 'kind': kind, 'park': park, 'school': school, 'comment': comment}

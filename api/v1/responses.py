"""Responses for agents: summary, text answers, one question's GeoJSON, a signed
export link, moderation (change api-v2-responses, #409; epic #408).

Every read counts the export's sessions (`survey.response_scope`), so the
numbers an agent reports equal the file a person downloads. The builders are
plain functions over (survey, scope, ...) -- the MCP tools call the same ones.
"""
from datetime import timedelta
from typing import Optional
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from survey import export as data_export
from survey import other_option
from survey import product_events as pe
from survey.analytics import (
    SessionValidationService, SurveyAnalyticsService, _get_ordered_sections, completed_session_filter,
)
from survey.audit import record as audit_record
from survey.models import Answer, Question, SurveySession
from survey.object_stats import object_aggregates
from survey.question_types import GEO_TYPES
from survey.response_scope import responses_scope

from .. import gates, limits, rights, scopes
from ..errors import VALIDATION, ApiError, not_found
from . import deps
from .auth import Bearer
from .docs import errors, list_errors
from .pagination import page
from .schemas import ExportLinkIn, ExportLinkOut, ModerateIn

from ninja import Router

router = Router(tags=['Responses'])

READ = Bearer(scopes.RESPONSES_READ)
MODERATE = Bearer(scopes.RESPONSES_MODERATE)

SKIPPED_TYPES = ('html', 'image')
TEXT_TYPES = ('text', 'text_line')
WRITE_INS_TOP = 50
GEOJSON_LIMIT = 5000
LINK_SALT = 'api.v1.export-link'
LINK_MAX_AGE = 15 * 60


# ─── Builders (shared with mcp/tools/responses.py) ────────────────────────────

def _choices(stat, question):
    current = {c['code'] for c in (question.choices or [])}
    return [{'code': code, 'label': label, 'count': count, 'current': code in current}
            for code, label, count in zip(stat['choice_codes'], stat['choice_labels'], stat['choice_counts'])]


def _write_ins(service, question):
    """The most frequent "other" texts: trimmed, grouped case-insensitively,
    shown as first written."""
    code = other_option.other_code(question)
    if code is None:
        return None
    counts, shown = {}, {}
    rows = (Answer.objects
            .filter(question_id__in=service._lineage_ids(question), selected_choices__contains=[code],
                    **service._session_filter())
            .exclude(text__isnull=True).exclude(text='')
            .order_by('pk')   # "first written" needs an order; heap order varies
            .values_list('text', flat=True))
    for text in rows:
        text = ' '.join(text.split())
        if not text:
            continue
        key = text.casefold()
        counts[key] = counts.get(key, 0) + 1
        shown.setdefault(key, text)
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:WRITE_INS_TOP]
    return [{'text': shown[k], 'count': n} for k, n in top]


def _question_entry(service, question, session_ids):
    entry = {'id': question.pk, 'code': question.code, 'section_id': question.survey_section_id,
             'name': question.name, 'type': question.input_type}
    if question.input_type == 'layer_objects':
        aggregates = object_aggregates(question, session_ids=session_ids)
        entry['answered'] = sum(a['answers'] for a in aggregates.values())
        entry['objects'] = [{'key': a['key'], 'title': a['title'], 'category': a['category'],
                             'answers': a['answers'], 'subs': list(a['subs'].values())}
                            for a in aggregates.values()]
        return entry
    stat = service.get_question_stats(question)
    kind = stat.get('type')
    if kind == 'choices':
        entry['answered'] = stat['total_answers']
        entry['choices'] = _choices(stat, question)
        write_ins = _write_ins(service, question)
        if write_ins is not None:
            entry['other_texts'] = write_ins
        if question.input_type == 'rating':
            total = sum(c['count'] for c in entry['choices'])
            weighted = sum(c['count'] * c['code'] for c in entry['choices'] if isinstance(c['code'], (int, float)))
            entry['mean'] = round(weighted / total, 2) if total else None
    elif kind == 'number':
        entry.update(answered=stat['count'], count=stat['count'], mean=stat['avg'], median=stat['median'],
                     min=stat['min_val'], max=stat['max_val'])
    elif kind == 'geo':
        entry['answered'] = stat['total_answers']
        entry['features'] = stat['total_answers']
        entry['subquestions'] = [_question_entry(service, sub, session_ids)
                                 for sub in question.subQuestions() if sub.input_type not in SKIPPED_TYPES]
    else:
        entry['answered'] = stat.get('total_answers', 0)
    return entry


def build_summary(survey, scope):
    sessions = scope.sessions
    session_ids = list(sessions.values_list('id', flat=True))
    responses = len(session_ids)
    completed = completed_session_filter(sessions, list(scope.headers)).count()
    service = SurveyAnalyticsService(survey, version=scope.version, sessions=sessions)
    questions = []
    for section in _get_ordered_sections(survey):
        for question in (Question.objects
                         .filter(survey_section=section, parent_question_id__isnull=True)
                         .order_by('order_number')):
            if question.input_type in SKIPPED_TYPES:
                continue
            questions.append(_question_entry(service, question, session_ids))
    return {
        'scope': scope.describe(),
        'responses': responses,
        'completed': completed,
        'completion_rate': round(100 * completed / responses) if responses else 0,
        'questions': questions,
    }


def text_answers(survey, question, scope, cursor=None, limit=50):
    if question.input_type not in TEXT_TYPES:
        raise ApiError(400, VALIDATION, 'Only text questions have text answers.',
                       fields={'question_id': ['not a text question']})
    service = SurveyAnalyticsService(survey, version=scope.version, sessions=scope.sessions)
    numbers = service.sequence_numbers()
    qs = (Answer.objects
          .filter(question_id__in=service._lineage_ids(question), text__isnull=False,
                  **service._session_filter())
          .exclude(text=''))
    items, next_cursor = page(qs, f'answers:{survey.uuid}:{question.pk}', cursor, limit)
    return {'items': [{'text': a.text, 'response': a.survey_session_id,
                       'number': numbers.get(a.survey_session_id)} for a in items],
            'next_cursor': next_cursor}


def question_geojson(question, scope, limit=GEOJSON_LIMIT):
    if question.input_type not in GEO_TYPES:
        raise ApiError(400, VALIDATION, 'Only map questions have GeoJSON.',
                       fields={'question_id': ['not a map question']})
    excluded = set(SurveySession.objects.filter(survey__in=scope.headers)
                   .exclude(id__in=scope.sessions).values_list('id', flat=True))
    collection, truncated = data_export.collect_question(question, scope.headers, excluded,
                                                         limit=min(limit, GEOJSON_LIMIT))
    collection['truncated'] = truncated
    return collection


def make_export_link(request, survey, params):
    """{url, expires_at}: the signed link a chat client can hand over."""
    token = signing.dumps({'s': str(survey.uuid), 'u': request.principal.user.pk,
                           't': request.principal.token_id, **params}, salt=LINK_SALT, compress=True)
    # The issuer is this deployment's own https origin (a preview's too);
    # build_absolute_uri would say http behind the proxy.
    url = settings.OAUTH_ISSUER.rstrip('/') + reverse('api_v1:export_link_download', args=[token])
    return {'url': url, 'expires_at': timezone.now() + timedelta(seconds=LINK_MAX_AGE)}


def set_status(request, survey, session_id, status, actor=None):
    # The editor's rule: the survey's own version family, never a trashed session.
    session = SurveySession.objects.filter(pk=session_id, survey__in=_family(survey), is_deleted=False).first()
    if session is None:
        raise not_found()
    old = session.validation_status or ''
    SessionValidationService().set_status(session, status)
    audit_record(actor or deps.actor(request), 'response_status', survey, session_id=session.pk, old=old,
                 new=status)
    return session


def _family(survey):
    return responses_scope(survey, None, include_all=True).headers


def _scope(survey, version, include_all, completed_only):
    try:
        return responses_scope(survey, version, include_all, completed_only)
    except (ValueError, LookupError):
        raise ApiError(400, VALIDATION, 'Unknown version.', fields={'version': ['unknown']})


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get('/surveys/{uuid}/responses/summary', auth=READ, openapi_extra=errors(400))
def summary(request, uuid: UUID, version: Optional[str] = None, include_all: bool = False,
            completed_only: bool = False):
    """Counts and per-question statistics over the sessions the export of the
    same parameters contains: no empty, deleted or rejected responses unless
    `include_all`. Sub-questions of map questions are nested under them."""
    survey = deps.survey(request, uuid)
    return build_summary(survey, _scope(survey, version, include_all, completed_only))


@router.get('/surveys/{uuid}/questions/{question_id}/answers', auth=READ, openapi_extra=list_errors())
def answers(request, uuid: UUID, question_id: int, version: Optional[str] = None, include_all: bool = False,
            completed_only: bool = False, cursor: Optional[str] = None, limit: int = 50):
    """Non-blank answers to one text question (or text sub-question), newest first."""
    survey = deps.survey(request, uuid)
    question = deps.question(request, survey, question_id)
    return text_answers(survey, question, _scope(survey, version, include_all, completed_only), cursor, limit)


@router.get('/surveys/{uuid}/questions/{question_id}/geojson', auth=READ, openapi_extra=errors(400))
def geojson(request, uuid: UUID, question_id: int, version: Optional[str] = None, include_all: bool = False,
            completed_only: bool = False):
    """One map question's answers as a CRS84 FeatureCollection, sub-question
    values as properties -- the export's GeoJSON layer. Stops at 5 000 features
    (`truncated: true`); the full set is the export."""
    survey = deps.survey(request, uuid)
    question = deps.question(request, survey, question_id)
    return question_geojson(question, _scope(survey, version, include_all, completed_only))


@router.post('/surveys/{uuid}/export-link', response=ExportLinkOut, auth=READ, openapi_extra=errors(400))
def export_link(request, uuid: UUID, body: ExportLinkIn):
    """A link to the export file, valid 15 minutes, for a person to open. Opening
    it checks again that you may read the survey and that its workspace is on Pro."""
    survey = deps.survey(request, uuid)
    refusal = data_export.check_format(body.format)
    if refusal:
        raise ApiError(400, VALIDATION, refusal, fields={'format': [refusal]})
    return make_export_link(request, survey, {
        'f': body.format, 'v': body.version, 'a': body.include_all, 'c': body.completed_only, 'x': body.files})


@router.get('/export-links/{token}', auth=None, url_name='export_link_download', include_in_schema=False)
def export_link_download(request, token: str):
    """The file behind an export link. No bearer: the signed link is the
    credential -- so every check the API makes is made again here."""
    from oauth2_provider.models import AccessToken
    from survey.email_verification import can_sign_in

    from ..auth import Principal
    try:
        data = signing.loads(token, salt=LINK_SALT, max_age=LINK_MAX_AGE)
    except signing.BadSignature:   # includes SignatureExpired
        raise not_found()
    access = (AccessToken.objects.select_related('user', 'profile', 'profile__organization')
              .filter(pk=data.get('t'), user_id=data.get('u')).first())
    profile = getattr(access, 'profile', None) if access else None
    if access is None or profile is None or profile.revoked_at is not None or not can_sign_in(access.user):
        raise not_found()
    principal = Principal(user=access.user, scopes=frozenset(access.scope.split()),
                          organization=profile.organization, token_id=access.pk, kind=profile.kind,
                          profile=profile)
    if not principal.has_scope(scopes.RESPONSES_READ):
        raise not_found()
    survey = rights.survey_for(principal, data.get('s'), min_role='viewer')
    gates.require_pro_api(principal, survey.organization)
    limits.hit(principal, 'export')
    pe.emit(pe.DATA_EXPORTED, access.user_id, {'survey_id': str(survey.id), 'format': data['f'],
                                               'surface': 'api_link'})
    return data_export.export_response(survey, data['f'], version=data.get('v'), include_all=bool(data.get('a')),
                                       completed_only=bool(data.get('c')), include_files=bool(data.get('x')))


@router.patch('/surveys/{uuid}/responses/{response_id}', auth=MODERATE, openapi_extra=errors())
def moderate(request, uuid: UUID, response_id: int, body: ModerateIn):
    """Approve, hold or reject a response (`""` clears the status). Rejected
    responses leave exports, summaries and public results; shared-map layers
    are rebuilt. Needs the editor role."""
    survey = deps.survey(request, uuid, role='editor')
    session = set_status(request, survey, response_id, body.validation_status)
    return {'id': session.pk, 'validation_status': session.validation_status or ''}

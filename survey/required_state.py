"""Required questions unanswered (change responses-required-unanswered, #691).

ONE definition of a session's *missing required questions*: the required top-level
questions of the session's own survey version that the session saw — the visibility
engine decides, on the operator surface for operator/paper sessions and the respondent
surface otherwise — and has no stored answer satisfying. *Completed* is "not empty and
nothing missing" (`analytics.completed_session_filter`).

The result is STORED on the session (`required_missing`, `required_complete`) because
the dashboard cards, the Overview, the export and the API count it over thousands of
sessions in a fixed number of queries. Everything that can change it calls this module:

- every section POST (`views.save_section_answers`), an inline answer edit, paper review,
  a ZIP import of responses — ``refresh(session)``;
- a question's `required`, minimum features or minimum objects changing, or a question
  with answers deleted — ``schedule_survey_refresh(header_id)``;
- the backfill migration — ``refresh_many(qs)``.

Publishing never needs a recompute: old sessions move to the archived header together
with the structure they were answered on.
"""
import logging

from django.db import transaction
from django.db.models import BooleanField, ExpressionWrapper, Q

from .question_types import MULTI_FEATURE_TYPES, SURFACE_OPERATOR, SURFACE_RESPONDENT

logger = logging.getLogger(__name__)

# Blocks that collect nothing are never required, whatever their stored flag says.
VALUELESS_TYPES = ('html', 'image')
CHUNK = 500
# A survey-wide recompute of up to this many non-empty sessions runs in the request
# that caused it (the creator sees the right numbers on the next page); a bigger one
# goes to the worker.
SYNC_LIMIT = 1000

_ROW_FIELDS = (
    'survey_session_id', 'question_id', 'question__code', 'question__input_type',
    'question__parent_question_id_id', 'layer_object_id', 'text', 'numeric',
    'selected_choices', 'upload_id', 'allocation', 'yn', 'has_geo',
)


def surface_of(session):
    """Whose form the session was answered on."""
    return SURFACE_OPERATOR if session.source != session.SOURCE_ONLINE else SURFACE_RESPONDENT


def _answer_rows(session_ids):
    """Top-level answer rows of these sessions, as dicts (one query)."""
    from .models import Answer
    has_geo = ExpressionWrapper(
        Q(point__isnull=False) | Q(line__isnull=False) | Q(polygon__isnull=False)
        | Q(multipoint__isnull=False),
        output_field=BooleanField(),
    )
    return (Answer.objects
            .filter(survey_session_id__in=session_ids, parent_answer_id__isnull=True)
            .annotate(has_geo=has_geo)
            .values(*_ROW_FIELDS))


def _has_value(row):
    """A row carries an answer. Inline editing can leave a blank row behind; it does
    not count."""
    if row['has_geo'] or row['upload_id'] or row['allocation'] or row['numeric'] is not None:
        return True
    if row['yn'] is not None or row['selected_choices']:
        return True
    return bool((row['text'] or '').strip())


def _answers_by_code(rows):
    """The visibility engine's input, read like ``answers_by_code_for_session``."""
    from .visibility import CONTROLLER_TYPES
    result = {}
    for row in rows:
        if row['question__input_type'] in CONTROLLER_TYPES and row['selected_choices']:
            codes = []
            for c in row['selected_choices']:
                try:
                    codes.append(int(c))
                except (TypeError, ValueError):
                    continue  # an unreadable stored code controls nothing
            result[row['question__code']] = codes
    return result


class _Survey:
    """One header's structure, loaded once for every session judged against it."""

    def __init__(self, header):
        from .models import Question
        from .visibility import VisibilityStructure
        self.header = header
        self.structure = VisibilityStructure(header)
        lo_ids = [q.id for qs in self.structure.questions_by_section.values()
                  for q in qs if q.input_type == 'layer_objects']
        self.collecting = set(
            Question.objects.filter(parent_question_id__in=lo_ids)
            .values_list('parent_question_id', flat=True)
        ) if lo_ids else set()

    def candidates(self, vmap):
        """Questions that can be missing, in survey order, under ``vmap``."""
        out = []
        for section in self.structure.sections:
            if not vmap.is_section_visible(section.id):
                continue
            for q in self.structure.questions_by_section[section.id]:
                if not vmap.is_question_visible(q.id):
                    continue
                if q.input_type == 'layer_objects':
                    # Its `required` is forced off; the minimum is the requirement.
                    if q.min_objects and q.id in self.collecting:
                        out.append(q)
                elif q.required and q.input_type not in VALUELESS_TYPES:
                    out.append(q)
        return out

    def missing(self, rows, surface, vmap=None):
        from .visibility import compute_visibility
        if vmap is None or vmap.surface != surface:
            vmap = compute_visibility(self.header, _answers_by_code(rows), surface=surface,
                                      structure=self.structure)
        valued = {}
        objects = {}
        for row in rows:
            if row['layer_object_id'] and row['question__parent_question_id_id']:
                objects.setdefault(row['question__parent_question_id_id'], set()).add(row['layer_object_id'])
            if _has_value(row):
                valued[row['question_id']] = valued.get(row['question_id'], 0) + 1
        missing = []
        for q in self.candidates(vmap):
            if q.input_type == 'layer_objects':
                ok = len(objects.get(q.id, ())) >= q.min_objects
            else:
                need = 1
                if q.input_type in MULTI_FEATURE_TYPES:
                    floor = (q.validation_settings or {}).get('min_features')
                    if isinstance(floor, int) and floor > 1:
                        need = floor
                ok = valued.get(q.id, 0) >= need
            if not ok:
                missing.append(q.code)
        return missing


def missing_required(session, *, vmap=None, answers=None):
    """Codes of the required questions ``session`` saw and left unanswered, in survey
    order. ``vmap``: the visibility map just computed for the session's stored answers
    (reused when it is for the session's surface). ``answers``: rows from
    ``_answer_rows`` already loaded. No writes."""
    rows = list(answers) if answers is not None else list(_answer_rows([session.id]))
    return _Survey(session.survey).missing(rows, surface_of(session), vmap=vmap)


def refresh(session, *, vmap=None):
    """Recompute and store ``session``'s state. Writes the two columns only (an
    UPDATE, never ``save()``), and mirrors them onto the instance."""
    from .models import SurveySession
    missing = missing_required(session, vmap=vmap)
    session.required_missing = missing
    session.required_complete = not missing
    SurveySession.objects.filter(pk=session.pk).update(
        required_missing=missing, required_complete=not missing)
    return missing


def refresh_many(sessions_qs):
    """Recompute every non-empty session of ``sessions_qs``: grouped by header, the
    structure loaded once per header, answers read per chunk of ``CHUNK``. Empty
    sessions are skipped (they are never completed, whatever their flag says).
    Returns the number of sessions written."""
    from .models import SurveyHeader, SurveySession
    from .analytics import nonempty_sessions
    rows = list(nonempty_sessions(sessions_qs).order_by('survey_id', 'id')
                .values_list('id', 'survey_id', 'source'))
    by_header = {}
    for sid, header_id, source in rows:
        by_header.setdefault(header_id, []).append((sid, source))
    written = 0
    headers = SurveyHeader.objects.in_bulk(list(by_header))
    for header_id, sessions in by_header.items():
        survey = _Survey(headers[header_id])
        for start in range(0, len(sessions), CHUNK):
            chunk = sessions[start:start + CHUNK]
            answers = {}
            for row in _answer_rows([sid for sid, _ in chunk]):
                answers.setdefault(row['survey_session_id'], []).append(row)
            updates = []
            for sid, source in chunk:
                surface = SURFACE_RESPONDENT if source == SurveySession.SOURCE_ONLINE else SURFACE_OPERATOR
                missing = survey.missing(answers.get(sid, []), surface)
                updates.append(SurveySession(pk=sid, required_missing=missing,
                                             required_complete=not missing))
            SurveySession.objects.bulk_update(updates, ['required_missing', 'required_complete'])
            written += len(updates)
    return written


def refresh_survey(header_id):
    """Recompute every session of one survey version."""
    from .models import SurveySession
    return refresh_many(SurveySession.objects.filter(survey_id=header_id))


def schedule_survey_refresh(header_id):
    """After the current transaction commits, recompute every session of
    ``header_id``: in this request for a survey of up to ``SYNC_LIMIT`` non-empty
    sessions, otherwise in the worker — inline when the task cannot be queued, so a
    refused enqueue never leaves stale state."""
    transaction.on_commit(lambda: _run_survey_refresh(header_id))


def _run_survey_refresh(header_id):
    from .models import SurveySession
    from .analytics import nonempty_sessions
    count = nonempty_sessions(SurveySession.objects.filter(survey_id=header_id)).count()
    if count <= SYNC_LIMIT:
        refresh_survey(header_id)
        return
    from .tasks import recompute_required_state
    try:
        recompute_required_state.delay(header_id)
    except Exception:  # noqa: BLE001 — broker down: recompute inline
        logger.exception('could not enqueue required-state recompute of %s; running inline', header_id)
        refresh_survey(header_id)

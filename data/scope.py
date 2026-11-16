"""Which sessions a surface counts (change data-scope, ADR-001 move 1).

ONE builder for every set-of-sessions read: public results and Site results blocks,
shared-map objects and tallies, object statistics, the export gate (and through it the API
and MCP response scopes), Responses. A surface names the switches it needs; it never writes
`is_deleted` or `validation_status` filters itself.

Owner decisions of 2026-11-14 (ADR-001 §6) live in the callers' choice of switches:
- the export keeps moderated and trashed sessions only with ``include_all`` (§6.1);
- public results count clean, non-empty sessions only (§6.2, ``SessionScope.public``);
- Responses keeps moderated sessions (``include_moderated=True``) and names them (§6.5).

Version resolution stays with the caller (``survey.versioning``): a scope takes survey ids.
"""
from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Q

MODERATED_STATUSES = ('on_hold', 'not_approved')


def _has_top_level_answer():
    """The ONE emptiness predicate (spec responses-empty-sessions): a session is non-empty
    when it has an Answer with ``parent_answer_id IS NULL``. Object answers are top-level rows
    and moderator-hidden answers are still rows, so both count."""
    from survey.models import Answer
    return Exists(Answer.objects.filter(
        survey_session_id=OuterRef('pk'), parent_answer_id__isnull=True,
    ))


def nonempty(qs):
    """Sessions of ``qs`` with at least one top-level answer."""
    return qs.filter(_has_top_level_answer())


def empty(qs):
    """Sessions of ``qs`` with no top-level answer."""
    return qs.filter(~_has_top_level_answer())


def moderation_counts(qs):
    """{'on_hold': n, 'not_approved': m} among the sessions of ``qs`` — what Responses
    names in its headline (ADR-001 §6.5)."""
    counts = dict.fromkeys(MODERATED_STATUSES, 0)
    rows = qs.filter(validation_status__in=MODERATED_STATUSES).values_list('validation_status', flat=True)
    for status in rows:
        counts[status] += 1
    return counts


@dataclass(frozen=True)
class SessionScope:
    """The sessions of ``survey_ids`` a surface counts.

    Without switches the scope is CLEAN: not trashed, not on hold, not rejected.
    - ``include_deleted``: keep trashed sessions;
    - ``include_moderated``: keep ``on_hold`` and ``not_approved`` sessions;
    - ``nonempty``: only sessions with a top-level answer;
    - ``completed``: only completed sessions — not empty, no required question left
      unanswered (the Responses overview's definition, `completed_session_filter`);
    - ``external_only``: only sessions opened by people outside the workspace.
    """
    survey_ids: frozenset
    include_deleted: bool = False
    include_moderated: bool = False
    nonempty: bool = False
    completed: bool = False
    external_only: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'survey_ids', frozenset(self.survey_ids))

    # ── constructors ─────────────────────────────────────────────────────

    @classmethod
    def for_family(cls, survey, **switches):
        """The survey's version family (canonical + archived versions, never the draft)."""
        from survey.versioning import family_ids
        return cls(family_ids(survey), **switches)

    @classmethod
    def public(cls, survey):
        """What every public aggregate counts: clean, non-empty sessions of the family."""
        return cls.for_family(survey, nonempty=True)

    def replace(self, **switches):
        """The same scope with some switches changed."""
        values = {
            'include_deleted': self.include_deleted, 'include_moderated': self.include_moderated,
            'nonempty': self.nonempty, 'completed': self.completed,
            'external_only': self.external_only,
        }
        values.update(switches)
        return SessionScope(self.survey_ids, **values)

    # ── reads ────────────────────────────────────────────────────────────

    def sessions(self):
        """The SurveySession queryset of this scope."""
        from survey.models import SurveySession
        qs = SurveySession.objects.filter(survey_id__in=self.survey_ids)
        qs = qs.filter(self._row_q(''))
        if self.nonempty:
            qs = nonempty(qs)
        if self.completed:
            from survey.analytics import completed_session_filter
            qs = completed_session_filter(qs)
        return qs

    def ids(self):
        return set(self.sessions().values_list('id', flat=True))

    def q(self, prefix):
        """A Q for rows related to a session through ``prefix`` (``survey_session`` on
        Answer, ``source_session`` on LayerObject). Field switches become lookups; the
        nonempty and completed switches become one ``__in`` subquery, so a related query
        never restates the rule."""
        q = self._row_q(prefix + '__') & Q(**{f'{prefix}__survey_id__in': self.survey_ids})
        if self.nonempty or self.completed:
            q &= Q(**{f'{prefix}__in': self.sessions().values('pk')})
        return q

    def related_q(self, prefix):
        """Like ``q`` but without the survey restriction — for a related query already
        narrowed to the right survey or layer (a shared map's objects, a question's answers,
        which may belong to a draft copy outside the family)."""
        q = self._row_q(prefix + '__')
        if self.nonempty or self.completed:
            from survey.models import SurveySession
            sub = nonempty(SurveySession.objects.filter(self._row_q('')))
            if self.completed:
                sub = sub.filter(required_complete=True)
            q &= Q(**{f'{prefix}__in': sub.values('pk')})
        return q

    def _row_q(self, p):
        from survey.models import SurveySession
        q = Q()
        if not self.include_deleted:
            q &= Q(**{f'{p}is_deleted': False})
        if not self.include_moderated:
            q &= ~Q(**{f'{p}validation_status__in': MODERATED_STATUSES})
        if self.external_only:
            q &= Q(**{f'{p}opened_by_kind': SurveySession.OPENED_BY_EXTERNAL})
        return q

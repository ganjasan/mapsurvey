"""The sessions an API read counts (change api-v2-responses, D1).

The summary, the text answers, the per-question GeoJSON and the export link
count exactly what the export of the same parameters contains, so an agent's
numbers always equal the file a person downloads. The set is built from the
export's own helpers -- `version_parts` and `excluded_sessions` -- never a
second definition.
"""
from dataclasses import dataclass

from .models import SurveySession


@dataclass(frozen=True)
class ResponseScope:
    version: str
    include_all: bool
    completed_only: bool
    headers: tuple
    sessions: object    # SurveySession queryset

    def describe(self):
        return {'version': self.version, 'include_all': self.include_all,
                'completed_only': self.completed_only}


def responses_scope(survey, version=None, include_all=False, completed_only=False):
    from .export import excluded_sessions, version_parts
    parts = version_parts(survey, version)
    excluded = excluded_sessions(parts, include_all, completed_only)
    headers = tuple(header for header, _prefix in parts)
    sessions = SurveySession.objects.filter(survey__in=headers).exclude(id__in=excluded)
    return ResponseScope(version=version or 'all', include_all=bool(include_all),
                         completed_only=bool(completed_only), headers=headers, sessions=sessions)

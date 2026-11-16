"""Saved Responses views (change data-analysis-views, #692).

A filter of the Responses table saved as a `DatasetView` of kind `responses` over the survey's
`responses` dataset. The table keys a question column by the database id of the lineage's
representative row, and publishing unpublished changes replaces the rows — so the stored state
names questions by CODE (`q:<code>`) and is translated to today's ids when a view is opened.

``config`` = {'version', 'required', 'q', 'sort', 'dir', 'columns': {<column>: <cf value>}} where a
column is a meta key of the table or ``q:<question code>`` and a value is the table's own filter
syntax (`v:a|b`, `r:min|max`, `d:from|to`, `t:text`). Not saved: the timeline brush, hidden rows,
the selection, column visibility and trash mode (design decision 7).
"""
import re

from data.models import Dataset, DatasetView

META_COLUMNS = ('id', 'start_datetime', 'duration', 'validation_status', 'source', 'required',
                'tags', 'language', 'version')
MAX_COLUMNS = 20
_VERSION = re.compile(r'^(all|draft|v\d{1,6})$')
_VALUE = re.compile(r'^[vrdt]:')


def _column_ok(key):
    return key in META_COLUMNS or (key.startswith('q:') and 2 < len(key) <= 60)


def clean_config(raw):
    """A stored state from anything dict-shaped; what it does not understand it drops."""
    raw = raw if isinstance(raw, dict) else {}
    version = str(raw.get('version') or 'all')
    required = str(raw.get('required') or '')
    sort = str(raw.get('sort') or '')
    columns = {}
    for key, value in (raw.get('columns') or {}).items() if isinstance(raw.get('columns'), dict) else ():
        key, value = str(key), str(value or '').strip()[:500]
        if _column_ok(key) and _VALUE.match(value) and len(value) > 2 and len(columns) < MAX_COLUMNS:
            columns[key] = value
    return {
        'version': version if _VERSION.match(version) else 'all',
        'required': required if required in ('missing', 'complete') else '',
        'q': str(raw.get('q') or '').strip()[:200],
        'sort': sort if _column_ok(sort) else '',
        'dir': 'asc' if raw.get('dir') == 'asc' else 'desc',
        'columns': columns,
    }


def is_empty(config):
    """Whether a state filters nothing: a sort or a version alone selects every response."""
    return not (config.get('required') or config.get('q') or config.get('columns'))


def responses_dataset(survey):
    """The `responses` dataset of a survey's canonical row, created when the registry has not met
    it yet (rows are otherwise written by the read-time `data.datasets.sync`)."""
    from survey.versioning import canonical_of
    canonical = canonical_of(survey)
    dataset, _created = Dataset.objects.get_or_create(
        kind=Dataset.KIND_RESPONSES, survey=canonical, question_code='',
        defaults=dict(organization_id=canonical.organization_id, name=(canonical.name or '')[:200],
                      privacy_class=Dataset.PRIVACY_AGGREGATED))
    return dataset


def _codes_by_id(service):
    """{question id as text: code} for every question row the table may key a column by."""
    return {str(qid): rep.code for qid, rep in service._rep_question_by_qid().items() if rep.code}


def _ids_by_code(service):
    """{code: representative id as text} — the column key the table uses today."""
    out = {}
    for rep in service._rep_question_by_qid().values():
        if rep.code and rep.parent_question_id_id is None:
            out.setdefault(rep.code, str(rep.id))
    return out


def _to_column(key, codes):
    if key in META_COLUMNS:
        return key
    code = codes.get(key)
    return f'q:{code}' if code else None


def config_from_params(params, service):
    """The table's request parameters (`sort`, `dir`, `required`, `q`, `version`, `cf_<key>`) as a
    stored state, question ids replaced by codes. Columns of unknown ids are dropped."""
    codes = _codes_by_id(service)
    columns = {}
    for key, value in params.items():
        if key.startswith('cf_') and str(value).strip():
            column = _to_column(key[3:], codes)
            if column:
                columns[column] = value
    return clean_config({
        'version': params.get('version') or 'all', 'required': params.get('required'),
        'q': params.get('q'), 'sort': _to_column(str(params.get('sort') or ''), codes) or '',
        'dir': params.get('dir'), 'columns': columns,
    })


def params_from_config(config, service):
    """A stored state as the table's request parameters, codes replaced by today's column ids. A
    column whose question is gone from the scope is left out."""
    config = clean_config(config)
    ids = _ids_by_code(service)

    def key_of(column):
        if column in META_COLUMNS:
            return column
        return ids.get(column[2:]) if column.startswith('q:') else None

    params = {}
    if config['required']:
        params['required'] = config['required']
    if config['q']:
        params['q'] = config['q']
    sort = key_of(config['sort']) if config['sort'] else None
    if sort:
        params['sort'], params['dir'] = sort, config['dir']
    for column, value in config['columns'].items():
        key = key_of(column)
        if key:
            params[f'cf_{key}'] = value
    return params


def view_for(survey, view_id):
    """The saved Responses view `view_id` of this survey, or None (another survey's, another kind)."""
    from survey.versioning import canonical_of
    try:
        view_id = int(view_id)
    except (TypeError, ValueError):
        return None
    return (DatasetView.objects
            .filter(pk=view_id, kind=DatasetView.KIND_RESPONSES, dataset__kind=Dataset.KIND_RESPONSES,
                    dataset__survey=canonical_of(survey))
            .select_related('dataset').first())


def views_of(survey):
    """The survey's saved Responses views, by name."""
    from survey.versioning import canonical_of
    views = list(DatasetView.objects
                 .filter(kind=DatasetView.KIND_RESPONSES, dataset__kind=Dataset.KIND_RESPONSES,
                         dataset__survey=canonical_of(survey))
                 .select_related('dataset__survey').order_by('name', 'id'))
    for view in views:
        view.open_url = open_url(view)
    return views


def open_url(view):
    """Where a saved view opens: the Responses page of its survey, its version, the table pane."""
    from django.urls import reverse
    survey = view.dataset.survey
    version = (view.config or {}).get('version') or 'all'
    query = f'?view={view.pk}' + (f'&version={version}' if version != 'all' else '')
    return reverse('editor_survey_analytics', args=[survey.uuid]) + query + '#responses'


def summary(view):
    """A short human line of what the view filters, for lists."""
    config = clean_config(view.config)
    parts = []
    if config['required'] == 'missing':
        parts.append('required unanswered')
    elif config['required'] == 'complete':
        parts.append('complete')
    if config['q']:
        parts.append('“%s”' % config['q'])
    for column, value in config['columns'].items():
        name = column[2:] if column.startswith('q:') else column
        parts.append('%s: %s' % (name, value[2:].replace('|', ', ')))
    if config['version'] != 'all':
        parts.append(config['version'])
    return ' · '.join(parts)

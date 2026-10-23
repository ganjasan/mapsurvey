"""JSON bodies of the API → the editor forms' data dialect.

The services validate by binding the editor's own forms, so this module only
renames and encodes: lists to the JSON strings hidden inputs post, booleans to
what `CheckboxInput` reads, `validation_settings` to the modal's `vs_*` keys,
choices to `choices_json`. It decides nothing -- every rule stays in the forms
and the services.
"""
import json

from survey.redirects import NO_REDIRECT

FALSE = 'false'   # CheckboxInput reads the string "false" as False


def _bool(value):
    return 'on' if value else FALSE


def survey_settings(body):
    """`SurveyHeaderForm` data for the fields `body` names."""
    data = {}
    if 'name' in body:
        data['name'] = body['name']
    if 'redirect_url' in body:
        url = body['redirect_url'] or NO_REDIRECT
        data['finish_action'] = 'thanks' if url == NO_REDIRECT else 'link'
        data['redirect_url'] = '' if url == NO_REDIRECT else url
    if 'languages' in body:
        data['available_languages'] = json.dumps(body['languages'])
    if 'visibility' in body:
        data['visibility'] = body['visibility']
    if 'basemaps' in body:
        data['basemaps'] = json.dumps(body['basemaps'])
    if 'default_basemap' in body:
        data['default_basemap'] = body['default_basemap'] or ''
    if 'show_branding' in body:
        data['show_branding'] = _bool(body['show_branding'])
    return data


SECTION_FIELDS = ('title', 'subheading', 'code', 'layout', 'next_label')


def section(body):
    return {k: ('' if body[k] is None else body[k]) for k in SECTION_FIELDS if k in body}


def translations(body):
    """{lang: {field: value}} with None as blank (a blank language loses its row)."""
    return {lang: {k: (v or '') for k, v in (values or {}).items()}
            for lang, values in (body.get('translations') or {}).items()}


VS_KEYS = ('min_value', 'max_value', 'outlier_sigma', 'min_length', 'area_outlier_factor',
           'max_dots', 'max_file_mb', 'max_files', 'min_features', 'max_features')


def question(body, *, create=False):
    """`QuestionForm` data + the modal's auxiliary keys for the fields `body` names."""
    data = {}
    for key in ('name', 'subtext', 'input_type', 'color', 'icon_class', 'display_style'):
        if key in body:
            data[key] = '' if body[key] is None else body[key]
    for key in ('required', 'share_with_respondents'):
        if key in body:
            data[key] = _bool(body[key])
    if 'layer_id' in body:
        data['layer'] = '' if body['layer_id'] is None else str(body['layer_id'])
    if 'min_objects' in body:
        data['min_objects'] = '' if body['min_objects'] is None else str(body['min_objects'])
    if 'choices' in body:
        data['choices_json'] = json.dumps(body['choices'] or [])
    if 'validation_settings' in body:
        vs = body['validation_settings'] or {}
        for key in VS_KEYS:
            data[f'vs_{key}'] = '' if vs.get(key) is None else str(vs[key])
    if create:
        # What the modal posts for a field the creator did not touch.
        data.setdefault('name', '')
        data.setdefault('color', '#000000')
        data.setdefault('display_style', 'default')
    return data


def visibility(body):
    """The rule as the services store it, or the UNSET marker when absent."""
    from survey.services.common import UNSET
    if 'visibility_rule' not in body:
        return UNSET
    rule = body['visibility_rule']
    if rule is None:
        return None
    return {k: v for k, v in rule.items() if v is not None}

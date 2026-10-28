"""The Translations tab (change translation-table, issue #454).

One page per survey: the table of `translation_table` for a source and a
target language, row saves over HTMX, the CSV export and import, and adding
a language from the page. Viewers read and export; editors save and import;
owners add languages (the Survey-settings rule). While a live survey has
unpublished changes the tab opens them, like Build.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from . import translation_table as tt
from .comments import open_counts as _thread_counts
from .models import CreatorPreferences
from .permissions import survey_permission_required
from .services import locks, surveys as svc_surveys
from .services.context import Actor
from .services.errors import ContentLocked, ValidationFailed
from .versioning import is_live, live_editing_enabled


def _languages(survey):
    langs = list(survey.available_languages or [])
    return langs, langs[1:]


def _pick_languages(request, survey):
    """(source, target) from `?from=`/`?to=`, with the defaults of spec
    translation-table: source = primary; target = the creator's interface
    language when the survey offers it as a translation, else the first one."""
    langs, targets = _languages(survey)
    if not targets:
        return None, None
    source = request.GET.get('from') or langs[0]
    if source not in langs:
        source = langs[0]
    target = request.GET.get('to') or ''
    if target not in targets:
        ui = ''
        prefs = CreatorPreferences.objects.filter(user=request.user).only('ui_language').first()
        if prefs is not None:
            ui = (prefs.ui_language or '').split('-')[0]
        target = ui if ui in targets else targets[0]
    return source, target


def _draft_redirect(request, survey):
    if (live_editing_enabled() and is_live(survey)
            and request.effective_survey_role in ('editor', 'owner')):
        draft = survey.get_draft_copy()
        if draft is not None:
            url = reverse('editor_survey_translations', kwargs={'survey_uuid': draft.uuid})
            query = request.META.get('QUERY_STRING')
            return redirect(url + ('?' + query if query else ''))
    return None


def _page_context(request, survey, source, target):
    rows = tt.rows_for(tt.occurrences(survey, target, source_language=source))
    langs, targets = _languages(survey)
    can_edit = request.effective_survey_role in ('editor', 'owner')
    content_locked, structure_locked = locks.locks(survey)
    return {
        'survey': survey,
        'rows': rows,
        'counts': tt.counts(rows),
        'languages': langs,
        'languages_json': json.dumps(langs),
        'primary': langs[0],
        'targets': targets,
        'source': source,
        'target': target,
        'can_edit': can_edit and not content_locked,
        'is_owner': request.effective_survey_role == 'owner',
        'content_locked': content_locked,
        'is_live': structure_locked,
        'thread_counts': _thread_counts(survey, request.user),
        'effective_role': request.effective_survey_role,
        'export_url': reverse('editor_survey_translations_export', kwargs={'survey_uuid': survey.uuid})
                      + f'?from={source}&to={target}',
    }


@survey_permission_required('viewer')
def translations_page(request, survey_uuid):
    survey = request.survey
    bounce = _draft_redirect(request, survey)
    if bounce is not None:
        return bounce
    source, target = _pick_languages(request, survey)
    langs, _targets = _languages(survey)
    if target is None:
        return render(request, 'editor/survey_translations.html', {
            'survey': survey, 'rows': None, 'languages': langs, 'languages_json': json.dumps(langs),
            'primary': langs[0] if langs else 'en',
            'targets': [], 'is_owner': request.effective_survey_role == 'owner',
            'can_edit': False, 'thread_counts': _thread_counts(survey, request.user),
            'effective_role': request.effective_survey_role,
        })
    context = _page_context(request, survey, source, target)
    context['import_report'] = request.session.pop('translation_import_report', None)
    return render(request, 'editor/survey_translations.html', context)


@survey_permission_required('editor')
@require_POST
def translation_save(request, survey_uuid):
    """One row (group or occurrence key) over HTMX; answers the re-rendered row."""
    survey = request.survey
    key = (request.POST.get('key') or '').strip()
    source = request.POST.get('from') or ''
    target = request.POST.get('to') or ''
    langs, targets = _languages(survey)
    if target not in targets or not key:
        return HttpResponse(status=400)
    if source not in langs:
        source = langs[0]
    value = request.POST.get('value', '')
    try:
        report = tt.apply(Actor.from_request(request), survey, target, {key: value},
                          overwrite=True, clear_empty=True)
    except ContentLocked as err:
        return JsonResponse({'error': str(err)}, status=403)
    except ValidationFailed as err:
        return JsonResponse({'error': err.message or _('Could not save.')}, status=422)
    if report.unmatched:
        return JsonResponse({'error': _('This text is no longer in the survey. Reload the page.')}, status=409)
    rows = tt.rows_for(tt.occurrences(survey, target, source_language=source),
                       split_keys=set((request.POST.get('split') or '').split(',')))
    row = next((r for r in rows if r.key == key or any(o.key == key for o in r.occurrences)), None)
    if row is None:
        return JsonResponse({'error': _('Saved, but the row could not be re-rendered. Reload the page.')}, status=409)
    response = render(request, 'editor/partials/translation_row.html', {
        'survey': survey, 'row': row, 'source': source, 'target': target, 'primary': langs[0],
        'can_edit': True,
    })
    response['X-TT-Counts'] = json.dumps(tt.counts(rows))
    return response


@survey_permission_required('viewer')
@require_GET
def translations_export(request, survey_uuid):
    survey = request.survey
    source, target = _pick_languages(request, survey)
    if target is None:
        raise Http404
    rows = tt.rows_for(tt.occurrences(survey, target, source_language=source))
    data = tt.export_csv(rows)
    response = HttpResponse(data, content_type='text/csv; charset=utf-8')
    slug = ''.join(ch if ch.isalnum() or ch in '-_' else '-' for ch in (survey.name or 'survey'))[:60].strip('-') or 'survey'
    response['Content-Disposition'] = f'attachment; filename="{slug}-translations-{target}.csv"'
    return response


@survey_permission_required('editor')
@require_POST
def translations_import(request, survey_uuid):
    survey = request.survey
    langs, targets = _languages(survey)
    target = request.POST.get('to') or ''
    source = request.POST.get('from') or langs[0]
    if target not in targets:
        return HttpResponse(status=400)
    upload = request.FILES.get('file')
    back = reverse('editor_survey_translations', kwargs={'survey_uuid': survey.uuid}) + f'?from={source}&to={target}'
    if upload is None:
        request.session['translation_import_report'] = {'error': _('Choose a CSV file first.')}
        return redirect(back)
    parsed = tt.parse_csv(upload.read())
    rows = tt.rows_for(tt.occurrences(survey, target))
    values, unmatched = tt.values_from_csv(parsed, rows)
    try:
        report = tt.apply(Actor.from_request(request), survey, target, values,
                          overwrite=request.POST.get('overwrite') == '1')
    except ContentLocked as err:
        request.session['translation_import_report'] = {'error': str(err)}
        return redirect(back)
    request.session['translation_import_report'] = {
        'file': upload.name, 'filled': report.filled, 'overwritten': report.overwritten,
        'skipped': report.skipped, 'unmatched': unmatched[:50], 'unmatched_total': len(unmatched),
        'rows': len(parsed),
    }
    return redirect(back)


@survey_permission_required('owner')
@require_POST
def translation_add_language(request, survey_uuid):
    """Append one language to `available_languages` through the settings
    service (the one writer of that field) and open the table on it."""
    survey = request.survey
    code = (request.POST.get('language') or '').strip().lower()
    langs, _targets = _languages(survey)
    if not code or len(code) > 10 or not code.replace('-', '').isalpha():
        return JsonResponse({'error': _('Pick a language from the list.')}, status=400)
    if code not in langs:
        try:
            svc_surveys.update_settings(
                Actor.from_request(request), survey,
                {'available_languages': json.dumps(langs + [code])}, partial=True)
        except ContentLocked as err:
            return JsonResponse({'error': str(err)}, status=403)
        except ValidationFailed as err:
            return JsonResponse({'error': err.message or _('Could not add the language.')}, status=422)
    survey.refresh_from_db(fields=['available_languages'])
    langs = list(survey.available_languages or [])
    target = code if code != langs[0] else (langs[1] if len(langs) > 1 else '')
    url = reverse('editor_survey_translations', kwargs={'survey_uuid': survey.uuid})
    return JsonResponse({'redirect': url + (f'?from={langs[0]}&to={target}' if target else '')})

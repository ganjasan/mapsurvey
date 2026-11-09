"""The Translations tab of a site (change site-translations, #618).

The survey Translations tab (`translation_views.py`) over a site: the same table partials, page
script and CSV round trip, fed by `site_translations`. Members read and export; owners, admins and
editors of a workspace that may use Sites save, import and add languages.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from billing import trial as billing_trial

from . import site_translations as st
from . import sites
from . import translation_table as tt
from .models import CreatorPreferences
from .services import sites as site_service
from .services.context import Actor
from .services.errors import ValidationFailed
from .site_views import _can_act, _site


def _may_edit(site, membership):
    return _can_act(membership) and billing_trial.may(site.organization, sites.FEATURE)


def _pick(request, site):
    langs = st.languages(site)
    targets = langs[1:]
    if not targets:
        return langs[0], None
    source = request.GET.get('from') or langs[0]
    if source not in langs:
        source = langs[0]
    target = request.GET.get('to') or ''
    if target not in targets:
        prefs = CreatorPreferences.objects.filter(user=request.user).only('ui_language').first()
        ui = (getattr(prefs, 'ui_language', '') or '').split('-')[0]
        target = ui if ui in targets else targets[0]
    return source, target


@login_required
def editor_site_translations(request, uuid):
    site, membership = _site(request, uuid)
    langs = st.languages(site)
    source, target = _pick(request, site)
    ctx = {
        'site': site, 'languages': langs, 'languages_json': json.dumps(langs), 'primary': langs[0],
        'targets': langs[1:], 'source': source, 'target': target, 'rows': None,
        'can_edit': _may_edit(site, membership), 'can_add': _may_edit(site, membership),
    }
    if target is not None:
        rows = tt.rows_for(st.occurrences(site, target, source_language=source))
        ctx.update(rows=rows, counts=tt.counts(rows),
                   export_url=reverse('editor_site_translations_export', args=[site.uuid]) + f'?from={source}&to={target}',
                   import_report=request.session.pop('site_translation_import_report', None))
    return render(request, 'sites/translations.html', ctx)


@login_required
@require_POST
def editor_site_translation_save(request, uuid):
    """One row (group or occurrence key) over fetch; answers the re-rendered row."""
    site, membership = _site(request, uuid)
    if not _may_edit(site, membership):
        return HttpResponseForbidden()
    langs = st.languages(site)
    key = (request.POST.get('key') or '').strip()
    target = request.POST.get('to') or ''
    source = request.POST.get('from') or langs[0]
    if target not in langs[1:] or not key:
        return HttpResponse(status=400)
    if source not in langs:
        source = langs[0]
    try:
        report = st.apply(Actor.from_request(request), site, target, {key: request.POST.get('value', '')},
                          overwrite=True, clear_empty=True)
    except ValidationFailed as err:
        return JsonResponse({'error': err.message or _('Could not save.')}, status=422)
    if report.unmatched:
        return JsonResponse({'error': _('This text is no longer on the site. Reload the page.')}, status=409)
    site.refresh_from_db()
    rows = tt.rows_for(st.occurrences(site, target, source_language=source),
                       split_keys=set((request.POST.get('split') or '').split(',')))
    row = next((r for r in rows if r.key == key or any(o.key == key for o in r.occurrences)), None)
    if row is None:
        return JsonResponse({'error': _('Saved, but the row could not be re-rendered. Reload the page.')}, status=409)
    response = render(request, 'editor/partials/translation_row.html', {
        'site': site, 'row': row, 'source': source, 'target': target, 'primary': langs[0], 'can_edit': True})
    response['X-TT-Counts'] = json.dumps(tt.counts(rows))
    return response


@login_required
@require_GET
def editor_site_translations_export(request, uuid):
    site, _membership = _site(request, uuid)
    source, target = _pick(request, site)
    if target is None:
        raise Http404
    data = tt.export_csv(tt.rows_for(st.occurrences(site, target, source_language=source)))
    response = HttpResponse(data, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{site.slug}-translations-{target}.csv"'
    return response


@login_required
@require_POST
def editor_site_translations_import(request, uuid):
    site, membership = _site(request, uuid)
    if not _may_edit(site, membership):
        return HttpResponseForbidden()
    langs = st.languages(site)
    target = request.POST.get('to') or ''
    source = request.POST.get('from') or langs[0]
    if target not in langs[1:]:
        return HttpResponse(status=400)
    back = reverse('editor_site_translations', args=[site.uuid]) + f'?from={source}&to={target}'
    upload = request.FILES.get('file')
    if upload is None:
        request.session['site_translation_import_report'] = {'error': _('Choose a CSV file first.')}
        return redirect(back)
    parsed = tt.parse_csv(upload.read())
    values, unmatched = tt.values_from_csv(parsed, tt.rows_for(st.occurrences(site, target)))
    report = st.apply(Actor.from_request(request), site, target, values, overwrite=request.POST.get('overwrite') == '1')
    request.session['site_translation_import_report'] = {
        'file': upload.name, 'filled': report.filled, 'overwritten': report.overwritten, 'skipped': report.skipped,
        'unmatched': unmatched[:50], 'unmatched_total': len(unmatched), 'rows': len(parsed)}
    return redirect(back)


@login_required
@require_POST
def editor_site_translation_add_language(request, uuid):
    site, membership = _site(request, uuid)
    if not _may_edit(site, membership):
        return HttpResponseForbidden()
    code = (request.POST.get('language') or '').strip().lower()
    try:
        site_service.add_language(Actor.from_request(request), site, code)
    except ValidationFailed as err:
        return JsonResponse({'error': err.message}, status=400)
    langs = st.languages(site)
    target = code if code != langs[0] else (langs[1] if len(langs) > 1 else '')
    url = reverse('editor_site_translations', args=[site.uuid])
    return JsonResponse({'redirect': url + (f'?from={langs[0]}&to={target}' if target else '')})


@login_required
@require_POST
def editor_site_translation_remove_language(request, uuid):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    site_service.remove_language(Actor.from_request(request), site, request.POST.get('language') or '')
    return redirect('editor_site_translations', uuid=site.uuid)

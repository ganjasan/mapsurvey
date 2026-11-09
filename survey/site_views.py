"""The site builder (change landing-core, #576; epic #348).

`/editor/sites/` lists the active workspace's sites; `/editor/sites/<uuid>/` is
the builder. A site is authorised against ITS OWN workspace, never the active one:
owner / admin / editor act, viewers read, anyone else gets 404. Every change needs the
`sites` feature (plan or trial; creating one counts the trial use); unpublishing is
always allowed, so a lapsed workspace can still take its page down. All writes are plain
form posts that redirect back to the builder, except block reorder (JSON). Block data goes
through `sites.clean_block` and nothing else. A save of a published site re-screens it.
"""
import json

from django.conf.locale import LANG_INFO
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _, pgettext
from django.views.decorators.http import require_POST

from billing import trial as billing_trial
from billing.entitlements import for_organization
from billing.gates import feature_required

from . import basemaps, branding, site_events, sites, share
from .content_screening import is_site_held
from .models import Site, SiteBlock, SitePage, SiteSurvey, SiteUpdate, SurveyHeader
from .permissions import get_org_membership
from .services import sites as site_service
from .services.context import Actor
from .services.sites import CONTENT_LANGUAGES


def _timezones():
    from zoneinfo import available_timezones
    return sorted(z for z in available_timezones() if '/' in z and not z.startswith(('Etc/', 'SystemV/', 'US/')))


def language_choices():
    out = []
    for code in CONTENT_LANGUAGES:
        info = LANG_INFO.get(code) or LANG_INFO.get({'no': 'nb'}.get(code, code)) or {}
        out.append((code, info.get('name_local') or info.get('name') or code))
    return out


# ─── access ───────────────────────────────────────────────────────────────────

def _site(request, uuid):
    """(site, membership) for a member of the site's workspace; 404 for anyone else."""
    site = get_object_or_404(Site.objects.select_related('organization'), uuid=uuid)
    membership = get_org_membership(request.user, site.organization)
    if membership is None:
        raise Http404
    return site, membership


def _can_act(membership):
    return membership is not None and membership.role in sites.ACTING_ROLES


def _refusal(request, site, membership):
    """The response that refuses a change, or None when the member may make it."""
    if not _can_act(membership):
        return HttpResponseForbidden()
    if not billing_trial.may(site.organization, sites.FEATURE):
        return feature_required(request, site.organization, sites.FEATURE)
    return None


def _is_autosave(request):
    return request.POST.get('autosave') == '1'


def _block_fragments(request, site, membership, block):
    """The canvas shell, the outline row and the panel of one block, re-rendered."""
    ctx = _builder_context(request, site, membership)
    block = next(b for b in ctx['blocks'] if b.pk == block.pk)
    ctx.update(b=block, item=ctx['items'][block.pk])
    return {
        'block': render_to_string('sites/editor/_canvas_block.html', ctx, request=request),
        'outline': render_to_string('sites/editor/_outline_item.html', ctx, request=request),
        'panel': render_to_string('sites/editor/_block_panel.html', ctx, request=request),
    }


def _back(site, anchor='', select=None, page=None):
    from urllib.parse import urlencode
    url = reverse('editor_site', args=[site.uuid])
    query = {}
    if page is not None and not page.is_home:
        query['page'] = page.pk
    if select is not None:
        query['select'] = select
    if query:
        url += '?' + urlencode(query)
    return redirect(f'{url}#{anchor}' if anchor else url)


def _page_of(site, value):
    """The page `value` (a posted or queried id) names on this site; home when empty; 404 for any
    other site's page (change site-pages)."""
    value = str(value or '').strip()
    if not value:
        return sites.home_page(site)
    if not value.isdigit():
        raise Http404
    return get_object_or_404(SitePage, pk=int(value), site=site)


# ─── list and create ──────────────────────────────────────────────────────────

@login_required
def editor_sites(request):
    org = getattr(request, 'active_org', None)
    if org is None:
        return redirect('editor')
    membership = get_org_membership(request.user, org)
    if membership is None:
        return redirect('editor')
    from . import site_templates
    rows, templates = [], []
    for site in Site.objects.filter(organization=org).order_by('-updated_at'):
        if site.is_template:
            templates.append(site)
            continue
        rows.append({'site': site, 'held': is_site_held(site),
                     'surveys': site.survey_links.count()})
    return render(request, 'sites/list.html', {
        'org': org, 'rows': rows, 'templates': templates, 'starters': site_templates.starters(),
        'can_act': _can_act(membership), 'may_create': billing_trial.may(org, sites.FEATURE),
    })


@login_required
@require_POST
def editor_site_create(request):
    org = getattr(request, 'active_org', None)
    membership = get_org_membership(request.user, org) if org is not None else None
    if not _can_act(membership):
        return HttpResponseForbidden()
    # "New site" is one click (owner, 2026-11-08): no title asked first. The page opens with its
    # placeholder title selected on the canvas; the address follows the first real title
    # (sites.PLACEHOLDER_SLUG, see editor_site_settings).
    given = sites.clean_title(request.POST.get('title'))
    language = (request.LANGUAGE_CODE or 'en')[:2] if hasattr(request, 'LANGUAGE_CODE') else 'en'
    # "From a template" posts `template` = starter:<key> or site:<uuid> (change site-templates).
    template = request.POST.get('template') or ''
    try:
        if template.startswith('starter:'):
            site = site_service.create_from_template(Actor.from_request(request), org,
                                                     starter=template.split(':', 1)[1], language=language)
            given = ''
        elif template.startswith('site:'):
            source = Site.objects.filter(uuid=template.split(':', 1)[1] or None, organization=org, is_template=True).first()
            if source is None:
                raise Http404
            site = site_service.create_from_template(Actor.from_request(request), org, template=source)
            given = site.title
        else:
            site = site_service.create_site(Actor.from_request(request), org, title=given, language=language)
    except site_service.SitesFeatureRequired:
        return feature_required(request, org, sites.FEATURE)
    except site_service.ValidationFailed:
        return HttpResponseBadRequest('unknown template')
    billing_trial.flash_started(request, org)
    url = reverse('editor_site', args=[site.uuid])
    return redirect(url if given else url + '?new=1')


@login_required
@require_POST
def editor_site_duplicate(request, uuid):
    """A copy of the site to start the next engagement from (change site-duplicate, #607). A new
    site, so it is a Pro use like New site; the copy opens in the builder, unpublished."""
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    org = site.organization
    try:
        copy = site_service.duplicate_site(Actor.from_request(request), site)
    except site_service.SitesFeatureRequired:
        return feature_required(request, org, sites.FEATURE)
    billing_trial.flash_started(request, org)
    messages.success(request, _('This is a copy of “%(title)s”. It is not published.') % {'title': site.title})
    return redirect('editor_site', uuid=copy.uuid)


@login_required
@require_POST
def editor_site_save_template(request, uuid):
    """Save the site as a template of the workspace (change site-templates, #620)."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    template = site_service.save_as_template(Actor.from_request(request), site)
    messages.success(request, _('“%(title)s” is saved as a template. Start a new site from it with New site → From a template.')
                     % {'title': site.title})
    return redirect('editor_site', uuid=template.uuid)


# ─── builder ──────────────────────────────────────────────────────────────────

def _update_rows(site):
    """Every update of the site, drafts too, for the side-panel panes (`pane_id` = selection id)."""
    rows = list(sites.feed(site, drafts=True))
    for u in rows:
        u.pane_id = f'update:{u.pk}'
    return rows


def _builder_context(request, site, membership, page=None, **extra):
    org = site.organization
    page = page or _page_of(site, request.GET.get('page'))
    pages = sites.pages_for(site)
    blocks = sites.blocks_for(site, page)
    links = list(site.survey_links.select_related('survey').order_by('order', 'id'))
    linked_ids = {link.survey_id for link in links}
    cards = {}
    for block in blocks:
        if block.kind == 'survey' and block.site_survey is not None:
            cards[block.pk] = sites.survey_card(block.site_survey.survey)
    event_counts = {b.pk: (site_events.active(b).count(), site_events.seats_left(b))
                    for b in blocks if b.kind == 'event'}
    results_missing = {b.pk for b in blocks if b.kind == 'results' and b.site_survey is not None
                       and sites.results_question(b.site_survey.survey, b.data.get('question_code')) is None}
    may_edit = _can_act(membership) and billing_trial.may(org, sites.FEATURE)
    # One record per block for the canvas, the outline and the panel (change
    # landing-builder-redesign): the same card the public page draws, whether the public page
    # draws it at all, and why not.
    items = {}
    a11y, a11y_site = sites.a11y_issues(site, blocks)
    for b in blocks:
        # An updates block on the canvas shows drafts too (change site-updates).
        card = sites.updates_card(b, drafts=True) if b.kind == 'updates' else sites.block_card(b)
        if b.kind == 'updates' and card:
            sites.decorate_updates(site, card['updates'])
        # A block whose template needs a card (results, event, survey) and has none is drawn as a
        # placeholder, like an incomplete one.
        complete = sites.is_complete(b) and not (b.kind in ('results', 'event', 'survey') and card is None)
        warn = ''
        if b.kind == 'survey' and card is not None and card['state'] == sites.CARD_HIDDEN:
            warn = card['reason']
        elif b.kind == 'survey' and card is not None and card['state'] == sites.CARD_UPCOMING \
                and b.site_survey.survey.status in ('draft', 'testing'):
            warn = _('The survey is a draft: the card shows “Coming soon” until you publish it.')
        elif b.pk in results_missing:
            warn = _('The question was removed from the survey; the block is not shown.')
        elif not complete:
            warn = _('Not shown on the page until it is filled in.')
        items[b.pk] = {'card': card, 'complete': complete, 'warn': warn,
                       'label': sites.outline_label(b), 'a11y': a11y.get(b.pk, [])}
    ctx = {
        'org': org, 'site': site, 'blocks': blocks, 'cards': cards, 'results_missing': results_missing,
        # Pages (change site-pages): the rail's tabs, the page the canvas shows, room for more.
        'pages': pages, 'current_page': page, 'pages_full': len(pages) >= sites.PAGES_MAX,
        'page_block_counts': {p.pk: p.blocks.count() for p in pages},
        'other_pages': [p for p in pages if p.pk != page.pk],
        'sitepage_pane': f'sitepage:{page.pk}',
        'site_updates': _update_rows(site),
        'update_statuses': [('', _('No status')), ('included', _('Included')), ('partly', _('Partly included')),
                            ('not', _('Not included'))],
        'update_counts': [('3', '3'), ('5', '5'), ('10', '10'), ('0', _('All'))],
        'update_kinds': [('', _('News and “You said, we did”')), ('news', _('News')),
                         ('decision', _('You said, we did'))],
        # The public page menu, on the canvas too (same rule: two or more pages in the menu).
        'canvas_pages': sites.menu(pages, page, [])['pages'],
        'items': items, 'selected': request.GET.get('select', ''), 'last_pk': blocks[-1].pk if blocks else '',
        'basemap_table': basemaps.table_for(org),
        'event_counts': event_counts, 'timezones': _timezones(),
        'links': [(link, sites.survey_card(link.survey)) for link in links],
        'linkable': [s for s in sites.linkable_surveys(org) if s.pk not in linked_ids],
        'all_linkable': list(sites.linkable_surveys(org)),
        'can_act': _can_act(membership), 'may_edit': may_edit,
        'lapsed': _can_act(membership) and not may_edit,
        'held': is_site_held(site),
        'picker': sites.picker(),
        'kinds': {k: v[0] for k, v in sites.BLOCK_KINDS.items()},
        'icons': {k: v[1] for k, v in sites.BLOCK_KINDS.items()},
        'site_widths': [('narrow', pgettext('site width', 'Narrow')), ('standard', pgettext('site width', 'Standard')),
                        ('wide', pgettext('site width', 'Wide'))],
        'brand': branding.for_site(org),
        'compare_slots': [(0, 'before', _('Before'), 'before_label'), (1, 'after', _('After'), 'after_label')],
        'heading_sizes': [('l', pgettext('heading size', 'Large')), ('m', pgettext('heading size', 'Medium')),
                          ('s', pgettext('heading size', 'Small'))],
        'library': sites.library(),
        'languages': language_choices(),
        'basemap_choices': basemaps.choices_for(org),
        'results_choices': sites.results_choices(org),
        'chart_viz': [('auto', _('Bar chart')), ('pie', _('Pie')), ('donut', _('Donut')), ('table', _('Table'))],
        'map_viz': [('auto', _('Markers')), ('heatmap', _('Heatmap')), ('cluster', _('Clusters'))],
        'public_url': request.build_absolute_uri(reverse('site_public', args=[site.slug])),
        'review_url': _review_url(request, site) if not site.is_published else '',
        'a11y_site': a11y_site,
        'a11y_count': len(a11y_site) + sum(len(v) for v in a11y.values()),
        'a11y_blocks': [(b, sites.outline_label(b) or sites.BLOCK_KINDS[b.kind][0])
                        for b in blocks if b.pk in a11y],
        'block_errors': {}, 'block_posted': {}, 'settings_errors': {}, 'new_kind': request.GET.get('add', ''),
        'new_errors': {}, 'new_raw': {},
    }
    if ctx['new_kind'] not in sites.BLOCK_KINDS:
        ctx['new_kind'] = ''
    ctx.update(extra)
    return ctx


@login_required
def editor_site(request, uuid):
    site, membership = _site(request, uuid)
    return render(request, 'sites/builder.html', _builder_context(request, site, membership))


@login_required
@require_POST
def editor_site_settings(request, uuid):
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    post = request.POST
    values = {k: post[k] for k in site_service.SETTINGS_FIELDS if k in post}
    try:
        site_service.update_settings(Actor.from_request(request), site, values,
                                     cover=request.FILES.get('cover'), remove_cover=post.get('remove_cover') == '1')
    except site_service.ValidationFailed as exc:
        errors = {k: v[0] for k, v in exc.fields.items()}
        site.refresh_from_db()
        if _is_autosave(request):
            return JsonResponse({'ok': False, 'errors': errors}, status=422)
        ctx = _builder_context(request, site, membership, settings_errors=errors)
        return render(request, 'sites/builder.html', ctx, status=400)
    if _is_autosave(request):
        ctx = _builder_context(request, site, membership)
        return JsonResponse({
            'ok': True,
            'hero': render_to_string('sites/editor/_hero.html', ctx, request=request),
            'page_panel': render_to_string('sites/editor/_page_panel.html', ctx, request=request),
            'title': site.title, 'slug': site.slug, 'public_url': ctx['public_url'], 'width': site.width,
        })
    messages.success(request, _('Site settings saved.'))
    return _back(site, 'settings')


# ─── linked surveys ───────────────────────────────────────────────────────────

@login_required
@require_POST
def editor_site_survey_link(request, uuid):
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    survey = get_object_or_404(SurveyHeader, uuid=request.POST.get('survey') or None)
    if site_service.link_survey(Actor.from_request(request), site, survey) is None:
        raise Http404
    return _back(site, 'surveys')


@login_required
@require_POST
def editor_site_survey_unlink(request, uuid, link_id):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    # Unlinking only removes content; a lapsed workspace may still do it.
    link = get_object_or_404(SiteSurvey, pk=link_id, site=site)
    site_service.unlink_survey(Actor.from_request(request), site, link)
    return _back(site, 'surveys')


# ─── blocks ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
def editor_site_block_add(request, uuid):
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    kind = request.POST.get('kind', '')
    if kind not in sites.BLOCK_KINDS:
        return HttpResponseBadRequest('unknown kind')
    after = request.POST.get('after', '')
    page = _page_of(site, request.POST.get('page'))
    try:
        result = site_service.save_block(
            Actor.from_request(request), site, None, kind, request.POST, request.FILES,
            creating=request.POST.get('empty') == '1', lenient=_is_autosave(request), page=page)
    except site_service.BlockRefused as exc:
        ctx = _builder_context(request, site, membership, page=page, new_kind=kind, new_errors=exc.errors,
                               new_raw=dict(exc.raw, title=request.POST.get('title', ''),
                                            survey=request.POST.get('survey', '')))
        return render(request, 'sites/builder.html', ctx, status=400)
    if after.isdigit():
        site_service.move_after(site, result, int(after))
    elif after == 'top':
        site_service.move_after(site, result, None)
    return _back(site, result.anchor, select=result.pk, page=page)


@login_required
@require_POST
def editor_site_block_edit(request, uuid, block_id):
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    block = get_object_or_404(SiteBlock, pk=block_id, site=site)
    try:
        result = site_service.save_block(Actor.from_request(request), site, block, block.kind,
                                         request.POST, request.FILES, lenient=_is_autosave(request))
        errors = {}
    except site_service.BlockRefused as exc:
        errors, result = exc.errors, exc.raw
    if _is_autosave(request):
        if errors:
            return JsonResponse({'ok': False, 'errors': errors}, status=422)
        return JsonResponse(dict(ok=True, **_block_fragments(request, site, membership, result)))
    if errors:
        # Keep what the creator typed: the form re-renders from the posted values, not the saved ones.
        posted = dict(result, title=request.POST.get('title', ''))
        if str(posted.get('current', '')).isdigit():
            posted['current'] = int(posted['current'])
        if block.kind == 'map' and not posted.get('area'):
            posted['area'] = block.data.get('area')
        ctx = _builder_context(request, site, membership, page=block.page, block_errors={block.pk: errors},
                               block_posted={block.pk: posted})
        return render(request, 'sites/builder.html', ctx, status=400)
    return _back(site, block.anchor, select=block.pk, page=block.page)


@login_required
@require_POST
def editor_site_block_duplicate(request, uuid, block_id):
    """A copy right under the block: same kind, heading, data, picture, survey link and files
    (the stored files are shared; event registrations are not copied)."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    block = get_object_or_404(SiteBlock, pk=block_id, site=site)
    copy = site_service.duplicate_block(Actor.from_request(request), site, block)
    return _back(site, copy.anchor, select=copy.pk, page=copy.page)


@login_required
@require_POST
def editor_site_block_delete(request, uuid, block_id):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    block = get_object_or_404(SiteBlock, pk=block_id, site=site)
    page = block.page
    site_service.delete_block(Actor.from_request(request), site, block)
    return _back(site, 'blocks', page=page)


@login_required
@require_POST
def editor_site_blocks_reorder(request, uuid):
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    try:
        order = [int(x) for x in json.loads(request.body or b'{}').get('order', [])]
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('bad order')
    page = _page_of(site, request.GET.get('page'))
    try:
        site_service.reorder_blocks(Actor.from_request(request), site, order, page=page)
    except site_service.ValidationFailed:
        return HttpResponseBadRequest('order must list every block of this page once')
    return JsonResponse({'ok': True})


# ─── pages (change site-pages, #628) ──────────────────────────────────────────

@login_required
@require_POST
def editor_site_page_add(request, uuid):
    """One click: an untitled page at the end, selected."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    try:
        page = site_service.add_page(Actor.from_request(request), site)
    except site_service.ValidationFailed as exc:
        messages.error(request, ' '.join(str(m) for v in exc.fields.values() for m in v))
        return _back(site)
    return _back(site, select=f'sitepage:{page.pk}', page=page)


@login_required
@require_POST
def editor_site_page_edit(request, uuid, page_id):
    """A page's title, address and menu flag; autosaved (JSON / 422) like a block."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    page = get_object_or_404(SitePage, pk=page_id, site=site)
    values = {k: request.POST.get(k) for k in ('title', 'slug') if k in request.POST}
    if 'menu' in request.POST:  # the panel posts 0 then, when ticked, 1 (the last one wins)
        values['in_menu'] = request.POST.get('menu') == '1'
    try:
        site_service.update_page(Actor.from_request(request), site, page, values)
    except site_service.ValidationFailed as exc:
        errors = {k: ' '.join(str(m) for m in v) for k, v in exc.fields.items()}
        if _is_autosave(request):
            return JsonResponse({'ok': False, 'errors': errors}, status=422)
        messages.error(request, ' '.join(errors.values()))
        return _back(site, select=f'sitepage:{page.pk}', page=page)
    if _is_autosave(request):
        return JsonResponse({'ok': True, 'title': page.title, 'slug': page.slug, 'in_menu': page.in_menu,
                             'url': request.build_absolute_uri(sites.page_url(site, page))})
    return _back(site, select=f'sitepage:{page.pk}', page=page)


@login_required
@require_POST
def editor_site_pages_reorder(request, uuid):
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    try:
        order = [int(x) for x in json.loads(request.body or b'{}').get('order', [])]
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('bad order')
    try:
        site_service.reorder_pages(Actor.from_request(request), site, order)
    except site_service.ValidationFailed:
        return HttpResponseBadRequest('order must list every page of this site but home once')
    return JsonResponse({'ok': True})


@login_required
@require_POST
def editor_site_page_delete(request, uuid, page_id):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    page = get_object_or_404(SitePage, pk=page_id, site=site)
    try:
        site_service.delete_page(Actor.from_request(request), site, page)
    except site_service.ValidationFailed:
        return HttpResponseBadRequest('the home page cannot be deleted')
    return _back(site)


# ─── updates (change site-updates, #629) ──────────────────────────────────────

@login_required
@require_POST
def editor_site_update_add(request, uuid):
    """*Add news* / *Add "You said, we did"* in an updates block: a draft, opened in the side panel."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    page = _page_of(site, request.POST.get('page'))
    try:
        update = site_service.add_update(Actor.from_request(request), site, request.POST.get('kind', ''))
    except site_service.ValidationFailed:
        return HttpResponseBadRequest('kind must be news or decision')
    return _back(site, update.anchor, select=f'update:{update.pk}', page=page)


@login_required
@require_POST
def editor_site_update_edit(request, uuid, update_id):
    """An update's fields from its panel; autosaved (JSON / 422) like a block."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    update = get_object_or_404(SiteUpdate, pk=update_id, site=site)
    values = {k: request.POST.get(k) for k in site_service.UPDATE_FIELDS if k in request.POST}
    if 'published' in request.POST:  # the panel posts 0 then, when ticked, 1 (the last one wins)
        values['published'] = request.POST.get('published') == '1'
    try:
        site_service.save_update(Actor.from_request(request), site, update, values)
    except site_service.ValidationFailed as exc:
        errors = {k: ' '.join(str(m) for m in v) for k, v in exc.fields.items()}
        if _is_autosave(request):
            return JsonResponse({'ok': False, 'errors': errors}, status=422)
        messages.error(request, ' '.join(errors.values()))
    if _is_autosave(request):
        return JsonResponse({'ok': True, 'title': update.title, 'published': update.is_published})
    return _back(site, update.anchor, select=f'update:{update.pk}', page=_page_of(site, request.POST.get('page')))


@login_required
@require_POST
def editor_site_update_delete(request, uuid, update_id):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    update = get_object_or_404(SiteUpdate, pk=update_id, site=site)
    site_service.delete_update(Actor.from_request(request), site, update)
    return _back(site, page=_page_of(site, request.POST.get('page')))


@login_required
@require_POST
def editor_site_block_move(request, uuid, block_id):
    """*Move to page* in a block's Settings: the block goes to the end of the chosen page."""
    site, membership = _site(request, uuid)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    block = get_object_or_404(SiteBlock, pk=block_id, site=site)
    page = _page_of(site, request.POST.get('page'))
    site_service.move_block(Actor.from_request(request), site, block, page)
    return _back(site, block.anchor, select=block.pk, page=page)


# ─── publish, delete ──────────────────────────────────────────────────────────

@login_required
@require_POST
def editor_site_publish(request, uuid):
    site, membership = _site(request, uuid)
    action = request.POST.get('action')
    if action == 'unpublish':
        if not _can_act(membership):
            return HttpResponseForbidden()
        site_service.unpublish(Actor.from_request(request), site)
        messages.success(request, _('The site is unpublished. Its address shows “not available” now.'))
        return _back(site)
    refused = _refusal(request, site, membership)
    if refused is not None:
        return refused
    try:
        site_service.publish(Actor.from_request(request), site)
    except site_service.ValidationFailed as exc:
        messages.error(request, exc.message)
        return _back(site)
    messages.success(request, _('The site is published.'))
    return _back(site)


@login_required
@require_POST
def editor_site_delete(request, uuid):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    title = site.title
    site_service.delete_site(Actor.from_request(request), site)
    messages.success(request, _('“%(title)s” is deleted.') % {'title': title})
    return redirect('editor_sites')


# ─── public page ──────────────────────────────────────────────────────────────

def _event_notice(request):
    """{'block': id, 'status': ...} from the redirect after a registration post, or None."""
    if request.GET.get('registered', '').isdigit():
        return {'block': int(request.GET['registered']), 'status': 'registered'}
    if request.GET.get('event', '').isdigit() and request.GET.get('event_error') in (
            'name', 'email', 'consent', 'full', 'closed'):
        return {'block': int(request.GET['event']), 'status': request.GET['event_error']}
    return None


def site_public(request, slug, page='', view='page', update_id=None):
    """/p/<slug>/ (the home page) and /p/<slug>/<page>/ (change site-pages); with `view='feed'` the update
    feed /p/<slug>/updates/ and with `view='update'` one update /p/<slug>/updates/<id>/ (change
    site-updates) — same access, header and menu, the feed in place of blocks. Published and not held →
    everyone; otherwise only members of the owning workspace, with a draft banner, and the
    survey-unavailable 404 for everyone else. The plan is never checked here: a site published
    under Pro survives a lapse."""
    site = Site.objects.select_related('organization').filter(slug=slug).first()
    if site is None:
        return render(request, 'survey_unavailable.html', status=404)
    held = is_site_held(site)
    live = site.is_published and not held and not site.is_template
    member = (request.user.is_authenticated
              and get_org_membership(request.user, site.organization) is not None)
    # A review link opens an unpublished draft for the client (change site-review-link) — never a
    # site held for a safety review, and never more than members already see.
    review = (not live and not member and not held
              and sites.review_token_ok(site, request.GET.get('review')))
    if not live and not member and not review:
        return render(request, 'survey_unavailable.html', status=404)
    # The visitor's language (change site-translations): ?lang=, the p_lang cookie, the browser,
    # then the primary. Fixed labels come from the respondent catalogs in that language.
    from types import SimpleNamespace

    from . import site_translations
    feed_updates, single = [], None
    if view == 'page':
        current = sites.page_for(site, page)
        if current is None:
            return render(request, 'survey_unavailable.html', status=404)
        path = sites.page_url(site, current)
    else:
        # The feed is what visitors see; one update opens for members while it is a draft (preview).
        rows = sites.feed(site)
        if view == 'update':
            single = sites.feed(site, drafts=member).filter(pk=update_id).first()
            if single is None:
                return render(request, 'survey_unavailable.html', status=404)
            feed_updates = [single]
            path = reverse('site_update_public', args=[site.slug, single.pk])
        else:
            feed_updates = list(rows)
            path = reverse('site_updates_public', args=[site.slug])
        current = None
    lang = site_translations.pick_language(request, site)
    offered = site_translations.languages(site)
    pages = sites.pages_for(site)
    page_url = share.base() + path
    review_token = request.GET.get('review', '') if review else ''
    with translation.override(lang):
        blocks = sites.page_blocks(site, current, lang=lang) if current is not None else []
        site_translations.localize(site, blocks, lang, pages=pages, updates=feed_updates)
        if current is not None:
            current = next(p for p in pages if p.pk == current.pk)
        else:
            current = SimpleNamespace(pk=None, is_home=False, slug='updates',
                                      title=single.title if single else _('Updates'))
        menu = sites.menu(pages, current, blocks)
        shown = list(feed_updates) + [u for b, c in blocks if b.kind == 'updates' and c for u in c['updates']]
        sites.decorate_updates(site, shown, lang=lang, review=review_token)
        for p, _on in menu['pages']:
            p.url = sites.page_url(site, p, lang=lang, review=review_token)
        response = render(request, 'sites/public.html', {
            'site': site, 'org': site.organization, 'blocks': blocks, 'lang': lang,
            'page': current, 'pages_menu': menu['pages'],
            'updates_view': view if view != 'page' else '', 'feed_updates': feed_updates,
            'feed_url': sites.updates_url(site, lang=lang, review=review_token),
            'home_url': sites.page_url(site, pages[0], lang=lang, review=review_token),
            'brand': branding.for_site(site.organization),
            'site_languages': [(code, dict(language_choices()).get(code, code)) for code in offered]
                              if len(offered) > 1 else [],
            'nav': menu['anchors'], 'preview': not live and not review, 'review': review, 'held': held,
            'map_layers': sites.map_layers(site, blocks),
            'media_script': any(b.kind in ('gallery', 'compare') for b, _c in blocks),
            'results': [card for b, card in blocks if b.kind == 'results'],
            'results_basemaps': (basemaps.table_for(site.organization)
                                 if any(b.kind == 'results' and c.get('block_type') == 'map' for b, c in blocks)
                                 else {}),
            'noindex': not live or site.visibility == 'unlisted',
            'show_branding': not for_organization(site.organization).has('unbranded'),
            'page_url': page_url + (f'?lang={lang}' if lang != offered[0] else ''),
            'base_url': page_url,
            'event_notice': _event_notice(request),
        })
    if request.GET.get('lang') == lang and len(offered) > 1:
        response.set_cookie('p_lang', lang, max_age=180 * 86400, path='/p/', samesite='Lax',
                            secure=request.is_secure())
    if not live:
        response['Cache-Control'] = 'private, no-store'
        response['Referrer-Policy'] = 'no-referrer'  # the review token must not leak to outbound links
    return response


@login_required
@require_POST
def editor_site_review_link(request, uuid):
    """New review link: the old one stops working (change site-review-link)."""
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    site_service.new_review_link(Actor.from_request(request), site)
    return JsonResponse({'ok': True, 'url': _review_url(request, site)})


def _review_url(request, site):
    return request.build_absolute_uri(reverse('site_public', args=[site.slug])) + '?review=' + sites.review_token(site)


@login_required
def editor_site_qr(request, uuid):
    """QR code of a site's public address, for the builder's Share box."""
    site, _membership = _site(request, uuid)
    fmt = 'svg' if request.GET.get('format') == 'svg' else 'png'
    body, content_type = share.qr_image(share.base() + reverse('site_public', args=[site.slug]), fmt=fmt)
    response = HttpResponse(body, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{site.slug}-qr.{fmt}"'
    return response


# ─── events (change landing-events, #579) ─────────────────────────────────────

def _public_event(slug, block_id):
    """(site, block) for a published, not held site's event block; 404 otherwise."""
    site = Site.objects.filter(slug=slug, is_published=True).first()
    if site is None or is_site_held(site):
        raise Http404
    block = get_object_or_404(SiteBlock, pk=block_id, site=site, kind='event')
    return site, block


@require_POST
def site_event_register(request, slug, block_id):
    """A resident registers: honeypot → rate limit → form → locked insert → mail → back to the
    page with a notice. Nothing personal is logged."""
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    from django_ratelimit.core import get_usage, is_ratelimited

    site, block = _public_event(slug, block_id)
    back = sites.page_url(site, block.page)  # the page the event is on (change site-pages)
    if request.POST.get('website'):
        return redirect(f'{back}?registered={block.pk}#{block.anchor}')
    try:
        usage = get_usage(request, group='site_event', fn=None, key='survey.abuse.ratelimit_key',
                          rate=site_events.REGISTER_LIMIT, method='POST', increment=True)
        limited = bool(usage) and usage['count'] > usage['limit']
    except Exception:  # noqa: BLE001 — a cache outage must not block a registration
        limited = False
    if limited:
        return HttpResponse(_('Too many registrations from this connection. Please try again later.'),
                            status=429, headers={'Retry-After': '3600'})
    name = ' '.join((request.POST.get('name') or '').split())[:120]
    email = (request.POST.get('email') or '').strip()[:254]
    problem = ''
    try:
        validate_email(email)
    except ValidationError:
        problem = 'email'
    if not name:
        problem = 'name'
    if request.POST.get('consent') != '1':
        problem = 'consent'
    if problem:
        return redirect(f'{back}?event_error={problem}&event={block.pk}#{block.anchor}')
    from . import site_translations
    lang = request.POST.get('lang') or ''
    status, reg = site_events.register(block, name, email,
                                       language=lang if lang in site_translations.languages(block.site) else '')
    if status in (site_events.REGISTERED, site_events.ALREADY):
        site_events.queue_confirmation(reg)
        return redirect(f'{back}?registered={block.pk}#{block.anchor}')
    return redirect(f'{back}?event_error={status}&event={block.pk}#{block.anchor}')


def site_event_cancel(request, token):
    """GET names the event and offers Cancel; only POST cancels (mail scanners prefetch links)."""
    from .models import EventRegistration
    reg = get_object_or_404(EventRegistration.objects.select_related('block__site'), token=token)
    site = reg.block.site
    done = False
    if request.method == 'POST':
        site_events.cancel(reg)
        done = True
    with translation.override(reg.language or site.language):
        return render(request, 'sites/event_cancel.html', {
            'registration': reg, 'block': reg.block, 'site': site, 'done': done or reg.cancelled_at is not None,
            'back_url': sites.page_url(site, reg.block.page, lang=reg.language),
            'starts_at': site_events.starts_at(reg.block.data), 'tz': reg.block.data.get('tz') or 'UTC',
        })


def _attendee_access(request, uuid, block_id):
    site, membership = _site(request, uuid)
    if not _can_act(membership):
        return site, None, HttpResponseForbidden()
    block = get_object_or_404(SiteBlock, pk=block_id, site=site, kind='event')
    return site, block, None


@login_required
def editor_site_attendees(request, uuid, block_id):
    """The attendee list of one event: owner / admin / editor; no Pro needed (deleting people's
    data must stay possible after a lapse)."""
    site, block, refused = _attendee_access(request, uuid, block_id)
    if refused is not None:
        return refused
    if request.GET.get('format') == 'csv':
        response = HttpResponse(site_events.csv_bytes(block), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{site.slug}-event-{block.pk}.csv"'
        return response
    return render(request, 'sites/attendees.html', {
        'org': site.organization, 'site': site, 'event_block': block,
        'registrations': block.registrations.order_by('created_at', 'id'),
        'active': site_events.active(block).count(), 'seats_left': site_events.seats_left(block),
        'starts_at': site_events.starts_at(block.data), 'retention_days': site_events.RETENTION_DAYS,
    })


@login_required
@require_POST
def editor_site_attendees_remove(request, uuid, block_id):
    site, block, refused = _attendee_access(request, uuid, block_id)
    if refused is not None:
        return refused
    which = request.POST.get('registration')
    site_service.remove_registrations(Actor.from_request(request), block, None if which == 'all' else which)
    if which == 'all':
        messages.success(request, _('All registrations of this event are deleted.'))
    return redirect('editor_site_attendees', uuid=site.uuid, block_id=block.pk)

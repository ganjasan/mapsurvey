"""The landing page builder (change landing-core, #576; epic #348).

`/editor/landings/` lists the active workspace's landings; `/editor/landings/<uuid>/` is
the builder. A landing is authorised against ITS OWN workspace, never the active one:
owner / admin / editor act, viewers read, anyone else gets 404. Every change needs the
`landing_pages` feature (plan or trial; creating one counts the trial use); unpublishing is
always allowed, so a lapsed workspace can still take its page down. All writes are plain
form posts that redirect back to the builder, except block reorder (JSON). Block data goes
through `landings.clean_block` and nothing else. A save of a published landing re-screens it.
"""
import json

from django.conf.locale import LANG_INFO
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from billing import trial as billing_trial
from billing.entitlements import for_organization
from billing.gates import feature_required

from . import basemaps, landing_events, landings, product_events, share
from .content_screening import is_landing_held, screen_landing
from .models import Landing, LandingBlock, LandingFile, LandingSurvey, SurveyHeader
from .permissions import get_org_membership
from .versioning import canonical_of

# The survey-content language list (editor/partials/language_picker.html), for <html lang>
# and the page's own labels.
CONTENT_LANGUAGES = (
    'af am ar az be bg bn bs ca cs cy da de el en es et eu fa fi fr ga gl gu he hi hr hu hy id is it ja '
    'ka kk km kn ko ky lo lt lv mk ml mn mr ms my ne nl no pa pl pt ro ru si sk sl sq sr sv sw ta te tg '
    'th tk tl tr uk ur uz vi zh'
).split()


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

def _landing(request, uuid):
    """(landing, membership) for a member of the landing's workspace; 404 for anyone else."""
    landing = get_object_or_404(Landing.objects.select_related('organization'), uuid=uuid)
    membership = get_org_membership(request.user, landing.organization)
    if membership is None:
        raise Http404
    return landing, membership


def _can_act(membership):
    return membership is not None and membership.role in landings.ACTING_ROLES


def _refusal(request, landing, membership):
    """The response that refuses a change, or None when the member may make it."""
    if not _can_act(membership):
        return HttpResponseForbidden()
    if not billing_trial.may(landing.organization, landings.FEATURE):
        return feature_required(request, landing.organization, landings.FEATURE)
    return None


def _touched(landing):
    """After any saved change: bump `updated_at`, and re-screen a live landing."""
    Landing.objects.filter(pk=landing.pk).update(updated_at=timezone.now())
    if landing.is_published:
        screen_landing(landing, trigger='live_edit')


def _back(landing, anchor=''):
    url = reverse('editor_landing', args=[landing.uuid])
    return redirect(f'{url}#{anchor}' if anchor else url)


# ─── list and create ──────────────────────────────────────────────────────────

@login_required
def editor_landings(request):
    org = getattr(request, 'active_org', None)
    if org is None:
        return redirect('editor')
    membership = get_org_membership(request.user, org)
    if membership is None:
        return redirect('editor')
    rows = []
    for landing in Landing.objects.filter(organization=org).order_by('-updated_at'):
        rows.append({'landing': landing, 'held': is_landing_held(landing),
                     'surveys': landing.survey_links.count()})
    return render(request, 'landings/list.html', {
        'org': org, 'rows': rows, 'can_act': _can_act(membership),
        'may_create': billing_trial.may(org, landings.FEATURE),
    })


@login_required
@require_POST
def editor_landing_create(request):
    org = getattr(request, 'active_org', None)
    membership = get_org_membership(request.user, org) if org is not None else None
    if not _can_act(membership):
        return HttpResponseForbidden()
    title = landings.clean_title(request.POST.get('title')) or _('Untitled landing page')
    if not billing_trial.use(org, landings.FEATURE, actor=request.user):
        return feature_required(request, org, landings.FEATURE)
    billing_trial.flash_started(request, org)
    landing = Landing.objects.create(
        organization=org, title=title, slug=landings.unique_slug(title), created_by=request.user,
        language=(request.LANGUAGE_CODE or 'en')[:2] if hasattr(request, 'LANGUAGE_CODE') else 'en',
    )
    product_events.emit('landing_created', request.user.pk, {
        'organization_id': org.pk, 'landing_id': landing.pk})
    return _back(landing)


# ─── builder ──────────────────────────────────────────────────────────────────

def _builder_context(request, landing, membership, **extra):
    org = landing.organization
    blocks = landings.blocks_for(landing)
    links = list(landing.survey_links.select_related('survey').order_by('order', 'id'))
    linked_ids = {link.survey_id for link in links}
    cards = {}
    for block in blocks:
        if block.kind == 'survey' and block.landing_survey is not None:
            cards[block.pk] = landings.survey_card(block.landing_survey.survey)
    event_counts = {b.pk: (landing_events.active(b).count(), landing_events.seats_left(b))
                    for b in blocks if b.kind == 'event'}
    results_missing = {b.pk for b in blocks if b.kind == 'results' and b.landing_survey is not None
                       and landings.results_question(b.landing_survey.survey, b.data.get('question_code')) is None}
    may_edit = _can_act(membership) and billing_trial.may(org, landings.FEATURE)
    ctx = {
        'org': org, 'landing': landing, 'blocks': blocks, 'cards': cards, 'results_missing': results_missing,
        'event_counts': event_counts, 'timezones': _timezones(),
        'links': [(link, landings.survey_card(link.survey)) for link in links],
        'linkable': [s for s in landings.linkable_surveys(org) if s.pk not in linked_ids],
        'all_linkable': list(landings.linkable_surveys(org)),
        'can_act': _can_act(membership), 'may_edit': may_edit,
        'lapsed': _can_act(membership) and not may_edit,
        'held': is_landing_held(landing),
        'picker': landings.picker(),
        'kinds': {k: v[0] for k, v in landings.BLOCK_KINDS.items()},
        'languages': language_choices(),
        'basemap_choices': basemaps.choices_for(org),
        'results_choices': landings.results_choices(org),
        'chart_viz': [('auto', _('Bar chart')), ('pie', _('Pie')), ('donut', _('Donut')), ('table', _('Table'))],
        'map_viz': [('auto', _('Markers')), ('heatmap', _('Heatmap')), ('cluster', _('Clusters'))],
        'public_url': request.build_absolute_uri(reverse('landing_public', args=[landing.slug])),
        'block_errors': {}, 'settings_errors': {}, 'new_kind': request.GET.get('add', ''),
        'new_errors': {}, 'new_raw': {},
    }
    if ctx['new_kind'] not in landings.BLOCK_KINDS:
        ctx['new_kind'] = ''
    ctx.update(extra)
    return ctx


@login_required
def editor_landing(request, uuid):
    landing, membership = _landing(request, uuid)
    return render(request, 'landings/builder.html', _builder_context(request, landing, membership))


@login_required
@require_POST
def editor_landing_settings(request, uuid):
    landing, membership = _landing(request, uuid)
    refused = _refusal(request, landing, membership)
    if refused is not None:
        return refused
    errors = {}
    title = landings.clean_title(request.POST.get('title'))
    if not title:
        errors['title'] = _('Give the page a title.')
    slug = (request.POST.get('slug') or '').strip().lower()
    slug_error = landings.slug_error(slug, landing) if slug != landing.slug else ''
    if slug_error:
        errors['slug'] = slug_error
    language = request.POST.get('language') or landing.language
    if language not in CONTENT_LANGUAGES:
        language = landing.language
    visibility = request.POST.get('visibility')
    if visibility not in ('public', 'unlisted'):
        visibility = landing.visibility
    cover = request.FILES.get('cover')
    cover_error = landings.check_image(cover)
    if cover_error:
        errors['cover'] = cover_error
    if errors:
        ctx = _builder_context(request, landing, membership, settings_errors=errors)
        return render(request, 'landings/builder.html', ctx, status=400)

    landing.title = title
    landing.summary = ' '.join((request.POST.get('summary') or '').split())[:landings.SUMMARY_MAX]
    landing.cover_alt = ' '.join((request.POST.get('cover_alt') or '').split())[:200]
    landing.slug = slug
    landing.language = language
    landing.visibility = visibility
    if cover is not None:
        landing.cover = cover
    elif request.POST.get('remove_cover') == '1':
        landing.cover = None
    landing.save()
    _touched(landing)
    messages.success(request, _('Page settings saved.'))
    return _back(landing, 'settings')


# ─── linked surveys ───────────────────────────────────────────────────────────

def _link(landing, survey):
    """Link the canonical of `survey` (same workspace, linkable) and return the row, or None."""
    canonical = canonical_of(survey)
    if canonical.organization_id != landing.organization_id:
        return None
    if not landings.linkable_surveys(landing.organization).filter(pk=canonical.pk).exists():
        return None
    link, created = LandingSurvey.objects.get_or_create(
        landing=landing, survey=canonical,
        defaults={'order': landing.survey_links.count()})
    return link


@login_required
@require_POST
def editor_landing_survey_link(request, uuid):
    landing, membership = _landing(request, uuid)
    refused = _refusal(request, landing, membership)
    if refused is not None:
        return refused
    survey = get_object_or_404(SurveyHeader, uuid=request.POST.get('survey') or None)
    if _link(landing, survey) is None:
        raise Http404
    _touched(landing)
    return _back(landing, 'surveys')


@login_required
@require_POST
def editor_landing_survey_unlink(request, uuid, link_id):
    landing, membership = _landing(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    # Unlinking only removes content; a lapsed workspace may still do it.
    link = get_object_or_404(LandingSurvey, pk=link_id, landing=landing)
    link.delete()
    landings.renumber(list(landing.blocks.order_by('order', 'id')))
    _touched(landing)
    return _back(landing, 'surveys')


# ─── blocks ───────────────────────────────────────────────────────────────────

def _raw_block(kind, post):
    """The posted fields of a block form as the dict `clean_block` reads."""
    raw = {key: post.get(key, '') for key in ('body', 'alt', 'caption', 'label', 'url', 'style',
                                              'button_label', 'description', 'current', 'color', 'basemap',
                                              'viz', 'date', 'start', 'end', 'tz', 'place', 'place_url',
                                              'capacity', 'open')}
    if kind == 'faq':
        raw['items'] = [{'q': q, 'a': a} for q, a in zip(post.getlist('q'), post.getlist('a'))]
    elif kind == 'timeline':
        raw['items'] = [{'title': t, 'when': w, 'body': b} for t, w, b in
                        zip(post.getlist('phase_title'), post.getlist('phase_when'), post.getlist('phase_body'))]
    return raw


def _document_changes(request, block):
    """(renames {file: title}, removals [file], uploads [file], errors) for a documents block."""
    errors = {}
    existing = list(block.files.all()) if block is not None else []
    renames, removals = {}, []
    for f in existing:
        if request.POST.get(f'remove_{f.pk}') == '1':
            removals.append(f)
            continue
        title = ' '.join((request.POST.get(f'file_title_{f.pk}') or '').split())[:200]
        if title and title != f.title:
            renames[f] = title
    uploads = request.FILES.getlist('files')
    problems = [msg for msg in (landings.check_document(u) for u in uploads) if msg]
    if problems:
        errors['files'] = ' '.join(problems)
    kept = len(existing) - len(removals)
    if not problems and kept + len(uploads) == 0:
        errors['files'] = _('Add at least one file.')
    elif kept + len(uploads) > landings.DOCUMENTS_MAX:
        errors['files'] = _('A documents block holds at most 20 files.')
    return renames, removals, uploads, errors


def _results_target(landing, value):
    """(link, question code, result kind) from the picker's '<survey uuid>:<code>', linking the
    survey when it is one of the workspace's; (None, '', '') for anything else."""
    from .public_results import block_type_for_question
    uuid_part, _sep, code = value.partition(':')
    survey = SurveyHeader.objects.filter(uuid=uuid_part).first() if uuid_part and code else None
    if survey is None:
        return None, '', ''
    survey = canonical_of(survey)
    question = landings.results_question(survey, code)
    if question is None:
        return None, '', ''
    link = _link(landing, survey)
    if link is None:
        return None, '', ''
    return link, code, block_type_for_question(question)


def _save_block(request, landing, block, kind):
    """Validate the posted block and save it. Returns {field: error} or {}."""
    raw = _raw_block(kind, request.POST)
    map_upload = request.FILES.get('geojson_file') if kind == 'map' else None
    map_error = ''
    if kind == 'map':
        if map_upload is not None:
            raw['area'], map_error = landings.parse_geojson(map_upload)
        elif block is not None:
            raw['area'] = block.data.get('area')
    results_link = None
    if kind == 'results':
        results_link, raw['question_code'], raw['result_kind'] = _results_target(
            landing, request.POST.get('results_question') or '')
    data, errors = landings.clean_block(kind, raw, org=landing.organization)
    if map_error:
        errors['area'] = map_error
    renames, removals, uploads = {}, [], []
    if kind == 'documents':
        renames, removals, uploads, doc_errors = _document_changes(request, block)
        errors.update(doc_errors)
    upload = request.FILES.get('image')
    image_error = landings.check_image(upload)
    if image_error:
        errors['image'] = image_error
    if kind == 'image' and upload is None and not (block and block.image):
        errors['image'] = _('Choose a picture.')
    link = None
    if kind == 'survey':
        survey = SurveyHeader.objects.filter(uuid=request.POST.get('survey') or None).first() \
            if (request.POST.get('survey') or '').strip() else None
        if survey is not None:
            link = _link(landing, survey)
        if link is None:
            errors['survey'] = _('Pick one of this workspace’s surveys.')
    if errors:
        return errors, raw
    with transaction.atomic():
        if block is None:
            block = LandingBlock(landing=landing, kind=kind, order=landings.next_order(landing))
        block.title = landings.clean_title(request.POST.get('title'))
        block.data = data
        if kind == 'image' and upload is not None:
            block.image = upload
        if kind == 'survey':
            block.landing_survey = link
        if kind == 'results':
            block.landing_survey = results_link
        block.save()
        for f, title in renames.items():
            f.title = title
            f.save(update_fields=['title'])
        for f in removals:
            f.file.delete(save=False)
            f.delete()
        last = block.files.order_by('-order').values_list('order', flat=True).first()
        nxt = 0 if last is None else last + 1
        for i, up in enumerate(uploads):
            LandingFile.objects.create(block=block, file=up, title=landings.document_title(up.name),
                                       size=up.size, content_type=(up.content_type or '')[:100],
                                       order=nxt + i)
    _touched(landing)
    return {}, block


@login_required
@require_POST
def editor_landing_block_add(request, uuid):
    landing, membership = _landing(request, uuid)
    refused = _refusal(request, landing, membership)
    if refused is not None:
        return refused
    kind = request.POST.get('kind', '')
    if kind not in landings.BLOCK_KINDS:
        return HttpResponseBadRequest('unknown kind')
    errors, result = _save_block(request, landing, None, kind)
    if errors:
        ctx = _builder_context(request, landing, membership, new_kind=kind, new_errors=errors,
                               new_raw=dict(result, title=request.POST.get('title', ''),
                                            survey=request.POST.get('survey', '')))
        return render(request, 'landings/builder.html', ctx, status=400)
    return _back(landing, result.anchor)


@login_required
@require_POST
def editor_landing_block_edit(request, uuid, block_id):
    landing, membership = _landing(request, uuid)
    refused = _refusal(request, landing, membership)
    if refused is not None:
        return refused
    block = get_object_or_404(LandingBlock, pk=block_id, landing=landing)
    errors, result = _save_block(request, landing, block, block.kind)
    if errors:
        ctx = _builder_context(request, landing, membership, block_errors={block.pk: errors})
        return render(request, 'landings/builder.html', ctx, status=400)
    return _back(landing, block.anchor)


@login_required
@require_POST
def editor_landing_block_delete(request, uuid, block_id):
    landing, membership = _landing(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    block = get_object_or_404(LandingBlock, pk=block_id, landing=landing)
    block.delete()
    landings.renumber(list(landing.blocks.order_by('order', 'id')))
    _touched(landing)
    return _back(landing, 'blocks')


@login_required
@require_POST
def editor_landing_blocks_reorder(request, uuid):
    landing, membership = _landing(request, uuid)
    refused = _refusal(request, landing, membership)
    if refused is not None:
        return refused
    try:
        order = [int(x) for x in json.loads(request.body or b'{}').get('order', [])]
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('bad order')
    blocks = {b.pk: b for b in landing.blocks.all()}
    if sorted(order) != sorted(blocks):
        return HttpResponseBadRequest('order must list every block of this landing once')
    landings.renumber([blocks[pk] for pk in order])
    _touched(landing)
    return JsonResponse({'ok': True})


# ─── publish, delete ──────────────────────────────────────────────────────────

@login_required
@require_POST
def editor_landing_publish(request, uuid):
    landing, membership = _landing(request, uuid)
    action = request.POST.get('action')
    if action == 'unpublish':
        if not _can_act(membership):
            return HttpResponseForbidden()
        Landing.objects.filter(pk=landing.pk).update(is_published=False, updated_at=timezone.now())
        messages.success(request, _('The page is unpublished. Its address shows “not available” now.'))
        return _back(landing)
    refused = _refusal(request, landing, membership)
    if refused is not None:
        return refused
    first = landing.published_at is None
    landing.is_published = True
    landing.published_at = landing.published_at or timezone.now()
    landing.save(update_fields=['is_published', 'published_at', 'updated_at'])
    screen_landing(landing, trigger='publish')
    product_events.emit('landing_published', request.user.pk, {
        'organization_id': landing.organization_id, 'landing_id': landing.pk, 'first': first,
        'blocks': landing.blocks.count(), 'surveys': landing.survey_links.count(),
        'visibility': landing.visibility})
    messages.success(request, _('The page is published.'))
    return _back(landing)


@login_required
@require_POST
def editor_landing_delete(request, uuid):
    landing, membership = _landing(request, uuid)
    if not _can_act(membership):
        return HttpResponseForbidden()
    title = landing.title
    landing.delete()
    messages.success(request, _('“%(title)s” is deleted.') % {'title': title})
    return redirect('editor_landings')


# ─── public page ──────────────────────────────────────────────────────────────

def _event_notice(request):
    """{'block': id, 'status': ...} from the redirect after a registration post, or None."""
    if request.GET.get('registered', '').isdigit():
        return {'block': int(request.GET['registered']), 'status': 'registered'}
    if request.GET.get('event', '').isdigit() and request.GET.get('event_error') in (
            'name', 'email', 'consent', 'full', 'closed'):
        return {'block': int(request.GET['event']), 'status': request.GET['event_error']}
    return None


def landing_public(request, slug):
    """/p/<slug>/. Published and not held → everyone; otherwise only members of the owning
    workspace, with a draft banner, and the survey-unavailable 404 for everyone else. The
    plan is never checked here: a landing published under Pro survives a lapse."""
    landing = Landing.objects.select_related('organization').filter(slug=slug).first()
    if landing is None:
        return render(request, 'survey_unavailable.html', status=404)
    held = is_landing_held(landing)
    live = landing.is_published and not held
    member = (request.user.is_authenticated
              and get_org_membership(request.user, landing.organization) is not None)
    if not live and not member:
        return render(request, 'survey_unavailable.html', status=404)
    with translation.override(landing.language):
        blocks = landings.page_blocks(landing, lang=landing.language)
        response = render(request, 'landings/public.html', {
            'landing': landing, 'org': landing.organization, 'blocks': blocks,
            'nav': landings.nav_items(blocks), 'preview': not live, 'held': held,
            'map_layers': landings.map_layers(landing, blocks),
            'results': [card for b, card in blocks if b.kind == 'results'],
            'results_basemaps': (basemaps.table_for(landing.organization)
                                 if any(b.kind == 'results' and c.get('block_type') == 'map' for b, c in blocks)
                                 else {}),
            'noindex': not live or landing.visibility == 'unlisted',
            'show_branding': not for_organization(landing.organization).has('unbranded'),
            'page_url': share.base() + reverse('landing_public', args=[landing.slug]),
            'event_notice': _event_notice(request),
        })
    if not live:
        response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def editor_landing_qr(request, uuid):
    """QR code of a landing's public address, for the builder's Share box."""
    landing, _membership = _landing(request, uuid)
    fmt = 'svg' if request.GET.get('format') == 'svg' else 'png'
    body, content_type = share.qr_image(share.base() + reverse('landing_public', args=[landing.slug]), fmt=fmt)
    response = HttpResponse(body, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{landing.slug}-qr.{fmt}"'
    return response


# ─── events (change landing-events, #579) ─────────────────────────────────────

def _public_event(slug, block_id):
    """(landing, block) for a published, not held landing's event block; 404 otherwise."""
    landing = Landing.objects.filter(slug=slug, is_published=True).first()
    if landing is None or is_landing_held(landing):
        raise Http404
    block = get_object_or_404(LandingBlock, pk=block_id, landing=landing, kind='event')
    return landing, block


@require_POST
def landing_event_register(request, slug, block_id):
    """A resident registers: honeypot → rate limit → form → locked insert → mail → back to the
    page with a notice. Nothing personal is logged."""
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    from django_ratelimit.core import get_usage, is_ratelimited

    landing, block = _public_event(slug, block_id)
    back = reverse('landing_public', args=[landing.slug])
    if request.POST.get('website'):
        return redirect(f'{back}?registered={block.pk}#{block.anchor}')
    try:
        usage = get_usage(request, group='landing_event', fn=None, key='survey.abuse.ratelimit_key',
                          rate=landing_events.REGISTER_LIMIT, method='POST', increment=True)
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
    status, reg = landing_events.register(block, name, email)
    if status in (landing_events.REGISTERED, landing_events.ALREADY):
        landing_events.queue_confirmation(reg)
        return redirect(f'{back}?registered={block.pk}#{block.anchor}')
    return redirect(f'{back}?event_error={status}&event={block.pk}#{block.anchor}')


def landing_event_cancel(request, token):
    """GET names the event and offers Cancel; only POST cancels (mail scanners prefetch links)."""
    from .models import EventRegistration
    reg = get_object_or_404(EventRegistration.objects.select_related('block__landing'), token=token)
    landing = reg.block.landing
    done = False
    if request.method == 'POST':
        landing_events.cancel(reg)
        done = True
    with translation.override(landing.language):
        return render(request, 'landings/event_cancel.html', {
            'registration': reg, 'block': reg.block, 'landing': landing, 'done': done or reg.cancelled_at is not None,
            'starts_at': landing_events.starts_at(reg.block.data), 'tz': reg.block.data.get('tz') or 'UTC',
        })


def _attendee_access(request, uuid, block_id):
    landing, membership = _landing(request, uuid)
    if not _can_act(membership):
        return landing, None, HttpResponseForbidden()
    block = get_object_or_404(LandingBlock, pk=block_id, landing=landing, kind='event')
    return landing, block, None


@login_required
def editor_landing_attendees(request, uuid, block_id):
    """The attendee list of one event: owner / admin / editor; no Pro needed (deleting people's
    data must stay possible after a lapse)."""
    landing, block, refused = _attendee_access(request, uuid, block_id)
    if refused is not None:
        return refused
    if request.GET.get('format') == 'csv':
        response = HttpResponse(landing_events.csv_bytes(block), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{landing.slug}-event-{block.pk}.csv"'
        return response
    return render(request, 'landings/attendees.html', {
        'org': landing.organization, 'landing': landing, 'event_block': block,
        'registrations': block.registrations.order_by('created_at', 'id'),
        'active': landing_events.active(block).count(), 'seats_left': landing_events.seats_left(block),
        'starts_at': landing_events.starts_at(block.data), 'retention_days': landing_events.RETENTION_DAYS,
    })


@login_required
@require_POST
def editor_landing_attendees_remove(request, uuid, block_id):
    landing, block, refused = _attendee_access(request, uuid, block_id)
    if refused is not None:
        return refused
    which = request.POST.get('registration')
    if which == 'all':
        block.registrations.all().delete()
        messages.success(request, _('All registrations of this event are deleted.'))
    else:
        block.registrations.filter(pk=which or 0).delete()
    return redirect('editor_landing_attendees', uuid=landing.uuid, block_id=block.pk)

"""The comments drawer and its endpoints (spec survey-comment-threads).

Every endpoint needs a role on the survey — any role: a viewer discussing the
wording with us is the whole point. Deleting someone else's comment is the one
owner-only act. Responses are HTMX partials; the drawer shell lives in
editor_base.html and swaps the panel in.
"""
import json

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import comments as svc
from . import product_events as pe
from .models import Comment, CommentAttachment, CommentThread
from .permissions import survey_permission_required
from .versioning import canonical_of

COUNTS_CHANGED = 'threadCountsChanged'


def _trigger(resp, announce=None):
    """HX-Trigger with the badge refresh and, optionally, a screen-reader announcement."""
    if announce:
        resp['HX-Trigger'] = json.dumps({COUNTS_CHANGED: '', 'cmAnnounce': {'text': announce}})
    else:
        resp['HX-Trigger'] = COUNTS_CHANGED
    return resp


# ─── panel context ──────────────────────────────────────────────────────────

def _parse_anchor(raw):
    if not raw or ':' not in raw:
        return None, None
    kind, key = raw.split(':', 1)
    return (kind, key) if kind in svc.ANCHOR_KINDS else (None, None)


def _mentions_payload(survey):
    return [{'id': m.user_id, 'name': svc.display_name(m.user), 'email': m.user.email}
            for m in svc.mentionable_members(survey)]


def panel_context(request, survey, anchor=None, status='open', focus_thread=None, inline=False):
    """Everything `_comments_panel.html` needs.

    `anchor` is `(kind, key)` with the page's object id; when set, only that
    object's threads are listed and the composer opens a new thread on it.
    `focus_thread` (a CommentThread) overrides the anchor and is highlighted.
    """
    if focus_thread is not None:
        a = svc.resolve_anchor(focus_thread)
        threads = svc.threads_for(survey, status=None).filter(pk=focus_thread.pk) | \
            svc.threads_for(survey, status=None).filter(svc.anchor_filter_from_thread(focus_thread))
        threads = threads.distinct()
        anchor_obj, anchor_kind, anchor_key = a, a.kind, a.key
        status = 'all'
    elif anchor and anchor[0]:
        try:
            flt = svc.anchor_filter(survey, *anchor)
        except svc.AnchorError:
            raise Http404
        threads = svc.threads_for(survey, status=status).filter(flt)
        fields = svc.anchor_fields(survey, *anchor)
        probe = CommentThread(survey=canonical_of(survey), **fields)
        anchor_obj = svc.resolve_anchor(probe)
        anchor_kind, anchor_key = anchor[0], anchor[1]
    else:
        threads = svc.threads_for(survey, status=status)
        anchor_obj = anchor_kind = anchor_key = None

    threads = [svc.decorate(t) for t in threads]
    # Group by anchor, keeping the queryset's recency order for the first thread of each group.
    groups = []
    by_key = {}
    for t in threads:
        k = t.anchor.badge_key
        if k not in by_key:
            by_key[k] = {'anchor': t.anchor, 'threads': []}
            groups.append(by_key[k])
        by_key[k]['threads'].append(t)

    counts = svc.open_counts(survey, request.user)
    new_ids = svc.new_thread_ids(survey, request.user, svc.seen_at_for(request.user, survey))
    for t in threads:
        t.is_new = t.pk in new_ids
    # New threads first inside each group, then the drawer's recency order.
    for g in groups:
        g['threads'].sort(key=lambda t: (not t.is_new,))
    groups.sort(key=lambda g: (not any(t.is_new for t in g['threads']),))
    resolved_total = CommentThread.objects.filter(survey=canonical_of(survey), status='resolved').count()
    return {
        'survey': survey,
        'groups': groups,
        'anchor': anchor_obj,
        'anchor_kind': anchor_kind,
        'anchor_key': anchor_key,
        'status': status,
        'open_total': counts['total'],
        'new_total': len(new_ids),
        'resolved_total': resolved_total,
        'focus_thread_id': focus_thread.pk if focus_thread else None,
        'inline': inline,
        'mentions': _mentions_payload(survey),
        'effective_role': getattr(request, 'effective_survey_role', None),
        'user': request.user,
    }


# ─── reads ──────────────────────────────────────────────────────────────────

@survey_permission_required('viewer')
@require_GET
def threads_panel(request, survey_uuid):
    survey = request.survey
    status = request.GET.get('status', 'open')
    if status not in ('open', 'resolved', 'all'):
        status = 'open'
    focus = None
    thread_id = request.GET.get('thread')
    if thread_id and thread_id.isdigit():
        focus = CommentThread.objects.filter(pk=thread_id, survey=canonical_of(survey)).first()
        if focus is None:
            raise Http404
    anchor = _parse_anchor(request.GET.get('anchor'))
    ctx = panel_context(request, survey, anchor=anchor, status=status, focus_thread=focus)
    resp = render(request, 'editor/partials/_comments_panel.html', ctx)
    # Rendering the drawer is "I looked": the new-marks just drawn are the last
    # ones for this activity. Badges elsewhere on the page refresh from counts.
    svc.mark_seen(request.user, survey)
    resp['HX-Trigger'] = COUNTS_CHANGED
    return resp


@survey_permission_required('viewer')
@require_GET
def thread_counts(request, survey_uuid):
    return JsonResponse(svc.badge_counts_json(request.survey, request.user))


# ─── writes ─────────────────────────────────────────────────────────────────

def _thread_or_404(request, thread_id):
    return get_object_or_404(CommentThread, pk=thread_id, survey=canonical_of(request.survey))


def _thread_response(request, thread, status=200, announce=None):
    thread = svc.decorate(
        CommentThread.objects.select_related('survey', 'session', 'block', 'block__question')
        .prefetch_related('comments__author', 'comments__mentions', 'comments__attachments')
        .get(pk=thread.pk))
    resp = render(request, 'editor/partials/_comment_thread.html', {
        'survey': request.survey, 'thread': thread, 'focus_thread_id': thread.pk,
        'effective_role': request.effective_survey_role, 'user': request.user,
        'mentions': _mentions_payload(request.survey),
    }, status=status)
    return _trigger(resp, announce)


def _body_and_mentions(request):
    body = (request.POST.get('body') or '').strip()
    mention_ids = request.POST.getlist('mentions')
    files = request.FILES.getlist('files')
    return body, mention_ids, files


def _emit(event, request, thread):
    try:
        pe.emit(event, request.user.pk, {
            'survey_id': thread.survey_id,
            'organization_id': thread.survey.organization_id,
            'anchor_kind': thread.anchor_kind,
        })
    except Exception:  # noqa: BLE001 — analytics never breaks a request
        pass


@survey_permission_required('viewer')
@require_POST
def thread_create(request, survey_uuid):
    survey = request.survey
    kind, key = _parse_anchor(request.POST.get('anchor'))
    if kind is None:
        return HttpResponse('Pick a question, section, response or block first.', status=400)
    body, mention_ids, files = _body_and_mentions(request)
    if not body and not files:
        return HttpResponse('Write something first.', status=400)
    try:
        thread, comment = svc.open_thread(survey, request.user, kind, key, body, mention_ids, files)
    except svc.AnchorError:
        raise Http404
    except svc.AttachmentRejected as exc:
        return HttpResponse(exc.message, status=400)
    svc.notify(thread, comment, request.user)
    _emit(pe.COMMENT_THREAD_OPENED, request, thread)
    inline = request.POST.get('inline') == '1'
    ctx = panel_context(request, survey, anchor=(kind, key), status='all' if inline else 'open', inline=inline)
    resp = render(request, 'editor/partials/_comments_panel.html', ctx, status=201)
    svc.mark_seen(request.user, survey)
    return _trigger(resp, 'Comment posted')


@survey_permission_required('viewer')
@require_POST
def comment_reply(request, survey_uuid, thread_id):
    thread = _thread_or_404(request, thread_id)
    body, mention_ids, files = _body_and_mentions(request)
    if not body and not files:
        return HttpResponse('Write something first.', status=400)
    try:
        comment = svc.reply(thread, request.user, body, mention_ids, files)
    except svc.AttachmentRejected as exc:
        return HttpResponse(exc.message, status=400)
    svc.notify(thread, comment, request.user)
    _emit(pe.COMMENT_REPLY_POSTED, request, thread)
    return _thread_response(request, thread, status=201, announce='Reply posted')


@survey_permission_required('viewer')
@require_POST
def thread_resolve(request, survey_uuid, thread_id):
    thread = _thread_or_404(request, thread_id)
    svc.resolve(thread, request.user)
    _emit(pe.COMMENT_THREAD_RESOLVED, request, thread)
    return _thread_response(request, thread, announce='Thread resolved')


@survey_permission_required('viewer')
@require_POST
def thread_reopen(request, survey_uuid, thread_id):
    thread = _thread_or_404(request, thread_id)
    svc.reopen(thread, request.user)
    return _thread_response(request, thread, announce='Thread reopened')


@survey_permission_required('viewer')
@require_POST
def comment_delete(request, survey_uuid, thread_id, comment_id):
    thread = _thread_or_404(request, thread_id)
    comment = get_object_or_404(Comment, pk=comment_id, thread=thread)
    if not svc.can_delete(comment, request.user, request.effective_survey_role):
        return HttpResponse(status=403)
    svc.delete_comment(comment)
    return _thread_response(request, thread, announce='Comment deleted')


@survey_permission_required('viewer')
@require_POST
def comment_edit(request, survey_uuid, thread_id, comment_id):
    thread = _thread_or_404(request, thread_id)
    comment = get_object_or_404(Comment, pk=comment_id, thread=thread)
    if not svc.can_edit(comment, request.user):
        return HttpResponse(status=403)
    body = (request.POST.get('body') or '').strip()
    if not body:
        return HttpResponse('Write something first.', status=400)
    svc.edit_comment(comment, body)
    return _thread_response(request, thread, announce='Comment updated')


@survey_permission_required('viewer')
@require_GET
def attachment_download(request, survey_uuid, thread_id, comment_id, attachment_id):
    thread = _thread_or_404(request, thread_id)
    att = get_object_or_404(CommentAttachment, pk=attachment_id, comment_id=comment_id, comment__thread=thread)
    storage = att.file.storage
    # S3: the storage signs a short-lived URL; locally the file is streamed.
    if hasattr(storage, 'bucket_name'):
        return redirect(att.file.url)
    return FileResponse(att.file.open('rb'), as_attachment=att.kind != 'image',
                        filename=att.original_name, content_type=att.content_type or None)

"""Comment threads on survey objects (spec survey-comment-threads).

Everything that knows what a thread is anchored to lives here: turning a stored
anchor into a label and a link, counting open threads per row, deciding who a
notification goes to, and every write path. Views check permissions and call
in; a later agent posting on a thread calls the same functions.

The one rule that keeps threads alive across publishing: a thread's `survey`
is always the canonical header and question/section anchors are codes, resolved
against the canonical survey's *current* rows on every read. See
`CommentThread` for why.
"""
import mimetypes
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    Comment, CommentAttachment, CommentSeen, CommentThread, Membership, PublicResultsBlock,
    Question, SurveySection, SurveySession,
)
from .versioning import canonical_of, family_ids_with_draft

ANCHOR_KINDS = ('survey', 'question', 'section', 'session', 'block')
SURVEY_ANCHOR_KEY = 'all'

MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_ATTACHMENTS_PER_COMMENT = 10
ALLOWED_ATTACHMENT_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/heic',
    'application/pdf', 'text/plain', 'text/csv',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/zip', 'application/geo+json', 'application/json',
}


class AttachmentRejected(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class AnchorError(ValueError):
    """The posted anchor does not name an object of this survey."""


# ─── Anchors ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Anchor:
    kind: str
    key: str            # question/section code, session/block id as a string
    label: str          # "White (albino) squirrel", "Record your observations", "Response #12"
    exists: bool        # False once the object is gone (deleted question, hard-deleted block)
    path: str           # editor path that shows the object (no #thread fragment)
    object: object = None
    section_id: Optional[int] = None   # the section a question row lives in (for ?section=)

    @property
    def badge_key(self):
        return f'{self.kind}:{self.key}'


def _question_row(canonical, code):
    return (Question.objects
            .filter(survey_section__survey_header=canonical, code=code)
            .select_related('survey_section').first())


def _section_row(canonical, code):
    return SurveySection.objects.filter(survey_header=canonical, code=code).first()


def resolve_anchor(thread):
    """Label, editor path and liveness of a thread's anchor, resolved now."""
    canonical = canonical_of(thread.survey)
    uuid = canonical.uuid
    if thread.anchor_kind == 'survey':
        return Anchor('survey', SURVEY_ANCHOR_KEY, canonical.name, True,
                      reverse('editor_survey_detail', kwargs={'survey_uuid': uuid}), canonical)
    if thread.anchor_kind == 'question':
        q = _question_row(canonical, thread.question_code)
        if q is None:
            return Anchor('question', thread.question_code, thread.question_code, False,
                          reverse('editor_survey_detail', kwargs={'survey_uuid': uuid}))
        return Anchor('question', q.code, q.name or q.code, True,
                      reverse('editor_survey_detail', kwargs={'survey_uuid': uuid}) + f'?section={q.survey_section_id}',
                      q, q.survey_section_id)
    if thread.anchor_kind == 'section':
        s = _section_row(canonical, thread.section_code)
        if s is None:
            return Anchor('section', thread.section_code, thread.section_code, False,
                          reverse('editor_survey_detail', kwargs={'survey_uuid': uuid}))
        return Anchor('section', s.code, s.title or s.name, True,
                      reverse('editor_survey_detail', kwargs={'survey_uuid': uuid}) + f'?section={s.id}',
                      s, s.id)
    if thread.anchor_kind == 'session':
        sess = thread.session
        key = str(thread.session_id)
        return Anchor('session', key, f'Response #{session_seq(canonical, sess) if sess else key}', sess is not None,
                      reverse('editor_survey_analytics', kwargs={'survey_uuid': uuid}) + f'?session={key}',
                      sess)
    block = thread.block
    key = str(thread.block_id)
    if block is None:
        return Anchor('block', key, 'Block', False,
                      reverse('editor_survey_public_results', kwargs={'survey_uuid': uuid}))
    title = (block.custom_title or {}).get('en') if isinstance(block.custom_title, dict) else None
    if not title and block.question_id:
        title = block.question.name
    label = f'{block.get_block_type_display()} · {title}' if title else block.get_block_type_display()
    return Anchor('block', key, label, True,
                  reverse('editor_survey_public_results', kwargs={'survey_uuid': uuid}) + f'?block={key}',
                  block)


def session_seq(canonical, session):
    """The ordinal the Responses page prints for a session: its position among
    the family's kept sessions ordered by start time (analytics' `seq_by_id`)."""
    return (SurveySession.objects
            .filter(survey_id__in=family_ids_with_draft(canonical), is_deleted=False,
                    start_datetime__lte=session.start_datetime)
            .exclude(start_datetime=session.start_datetime, id__gt=session.id)
            .count())


def thread_path(thread, anchor=None):
    """Relative editor URL that opens the page with the drawer on this thread."""
    anchor = anchor or resolve_anchor(thread)
    return f'{anchor.path}#thread-{thread.pk}'


def anchor_fields(survey, kind, key):
    """Stored fields for a posted anchor, validated against this survey.

    `key` is the object's id as the page knows it (question/section/session/
    block id); question and section are translated to their code so the thread
    survives publishing. Raises AnchorError when the object is not part of the
    survey family.
    """
    canonical = canonical_of(survey)
    if kind == 'survey':
        return {'anchor_kind': 'survey'}
    try:
        pk = int(key)
    except (TypeError, ValueError):
        raise AnchorError('bad anchor')
    family = family_ids_with_draft(survey)
    if kind == 'question':
        q = Question.objects.filter(pk=pk, survey_section__survey_header_id__in=family).first()
        if q is None:
            raise AnchorError('question not in survey')
        return {'anchor_kind': 'question', 'question_code': q.code}
    if kind == 'section':
        s = SurveySection.objects.filter(pk=pk, survey_header_id__in=family).first()
        if s is None:
            raise AnchorError('section not in survey')
        return {'anchor_kind': 'section', 'section_code': s.code}
    if kind == 'session':
        sess = SurveySession.objects.filter(pk=pk, survey_id__in=family).first()
        if sess is None:
            raise AnchorError('session not in survey')
        return {'anchor_kind': 'session', 'session': sess}
    if kind == 'block':
        b = PublicResultsBlock.objects.filter(pk=pk, page__survey=canonical).first()
        if b is None:
            raise AnchorError('block not in survey')
        return {'anchor_kind': 'block', 'block': b}
    raise AnchorError('unknown anchor kind')


ANCHOR_FIELDS = ('question_code', 'section_code', 'session', 'block')


def _filter_from_fields(fields):
    q = Q(anchor_kind=fields['anchor_kind'])
    for name in ANCHOR_FIELDS:
        if fields.get(name):
            q &= Q(**{name: fields[name]})
    return q


def anchor_filter_from_thread(thread):
    """Queryset filter for every thread sharing this thread's anchor."""
    return _filter_from_fields({
        'anchor_kind': thread.anchor_kind, 'question_code': thread.question_code,
        'section_code': thread.section_code, 'session': thread.session_id and thread.session,
        'block': thread.block_id and thread.block,
    })


def anchor_filter(survey, kind, key):
    """Queryset filter for the threads of one anchor, given the page's id."""
    return _filter_from_fields(anchor_fields(survey, kind, key))


def decorate(thread):
    """Attach what the thread partial reads: `.anchor` and `.visible_comments`."""
    thread.anchor = resolve_anchor(thread)
    thread.visible_comments = list(thread.comments.all())
    return thread


# ─── Reads ──────────────────────────────────────────────────────────────────

def threads_for(survey, status='open'):
    qs = (CommentThread.objects.filter(survey=canonical_of(survey))
          .select_related('created_by', 'resolved_by', 'session', 'block', 'block__question')
          .prefetch_related('comments__author', 'comments__mentions', 'comments__attachments'))
    if status in ('open', 'resolved'):
        qs = qs.filter(status=status)
    return qs


def seen_at_for(user, survey):
    """When `user` last opened this survey's comments, or None (never)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    row = CommentSeen.objects.filter(user=user, survey=canonical_of(survey)).only('seen_at').first()
    return row.seen_at if row else None


def mark_seen(user, survey):
    if user is None or not getattr(user, 'is_authenticated', False):
        return
    CommentSeen.objects.update_or_create(user=user, survey=canonical_of(survey), defaults={'seen_at': timezone.now()})


def new_thread_ids(survey, user, since=None):
    """Threads with activity after `since` that the user did not write last.

    `since=None` (never looked) makes every thread with someone else's last
    comment new, which is the right first impression for a member who has just
    been added to the workspace.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return set()
    qs = CommentThread.objects.filter(survey=canonical_of(survey))
    if since is not None:
        qs = qs.filter(last_activity_at__gt=since)
    out = set()
    for t in qs.prefetch_related('comments'):
        live = [c for c in t.comments.all() if c.deleted_at is None]
        last = live[-1] if live else None
        actor_id = last.author_id if last is not None else t.created_by_id
        if t.status == 'resolved' and t.resolved_by_id == getattr(user, 'pk', None):
            continue
        if actor_id != getattr(user, 'pk', None):
            out.add(t.pk)
    return out


def open_counts(survey, user=None):
    """Open threads per row, one grouped query.

    Returns {'question': {code: n}, 'section': {code: n}, 'session': {id: n},
    'block': {id: n}, 'total': n, 'new_keys': {'kind:key', ...}, 'new_total': n}.
    A section's number includes the threads on the questions inside it, which
    is what tells a reader "something is waiting in here" from the sidebar.
    `new_keys` names the anchors with activity the user has not seen yet.
    """
    canonical = canonical_of(survey)
    rows = (CommentThread.objects.filter(survey=canonical, status='open')
            .values('anchor_kind', 'question_code', 'section_code', 'session_id', 'block_id')
            .annotate(n=Count('id')))
    out = {'survey': Counter(), 'question': Counter(), 'section': Counter(), 'session': Counter(), 'block': Counter(), 'total': 0}
    for r in rows:
        out['total'] += r['n']
        k = r['anchor_kind']
        if k == 'survey':
            out['survey'][SURVEY_ANCHOR_KEY] += r['n']
        elif k == 'question':
            out['question'][r['question_code']] += r['n']
        elif k == 'section':
            out['section'][r['section_code']] += r['n']
        elif k == 'session':
            out['session'][str(r['session_id'])] += r['n']
        elif k == 'block':
            out['block'][str(r['block_id'])] += r['n']
    if out['question']:
        # Roll question threads up into their section (sub-questions included).
        q_rows = (Question.objects
                  .filter(survey_section__survey_header=canonical, code__in=list(out['question']))
                  .values_list('code', 'survey_section__code'))
        for code, section_code in q_rows:
            out['section'][section_code] += out['question'][code]
    out['new_keys'] = set()
    out['new_total'] = 0
    if user is not None and getattr(user, 'is_authenticated', False):
        new_ids = new_thread_ids(survey, user, seen_at_for(user, survey))
        if new_ids:
            out['new_total'] = len(new_ids)
            q_to_section = {}
            for t in CommentThread.objects.filter(pk__in=new_ids).only('anchor_kind', 'question_code', 'section_code', 'session_id', 'block_id'):
                if t.anchor_kind == 'survey':
                    out['new_keys'].add(f'survey:{SURVEY_ANCHOR_KEY}')
                elif t.anchor_kind == 'question':
                    out['new_keys'].add(f'question:{t.question_code}')
                    q_to_section.setdefault(t.question_code, None)
                elif t.anchor_kind == 'section':
                    out['new_keys'].add(f'section:{t.section_code}')
                elif t.anchor_kind == 'session':
                    out['new_keys'].add(f'session:{t.session_id}')
                else:
                    out['new_keys'].add(f'block:{t.block_id}')
            if q_to_section:
                for code, section_code in (Question.objects
                                           .filter(survey_section__survey_header=canonical, code__in=list(q_to_section))
                                           .values_list('code', 'survey_section__code')):
                    out['new_keys'].add(f'section:{section_code}')
    return out


def unseen_by_survey(user, surveys):
    """{canonical survey id: (open threads, unseen threads)} for a dashboard list.

    One query for the threads, one for the seen marks; the "was the last word
    someone else's" check runs in Python over the prefetched comments. Sized
    for a dashboard of tens of surveys, not thousands.
    """
    ids = [canonical_of(s).id for s in surveys]
    if not ids or user is None or not getattr(user, 'is_authenticated', False):
        return {}
    seen = {r.survey_id: r.seen_at for r in CommentSeen.objects.filter(user=user, survey_id__in=ids)}
    out = {sid: [0, 0] for sid in ids}
    threads = (CommentThread.objects.filter(survey_id__in=ids)
               .only('survey_id', 'status', 'last_activity_at', 'created_by_id', 'resolved_by_id')
               .prefetch_related('comments'))
    for t in threads:
        if t.status == 'open':
            out[t.survey_id][0] += 1
        since = seen.get(t.survey_id)
        if since is not None and t.last_activity_at <= since:
            continue
        if t.status == 'resolved' and t.resolved_by_id == user.pk:
            continue
        live = [c for c in t.comments.all() if c.deleted_at is None]
        actor_id = live[-1].author_id if live else t.created_by_id
        if actor_id != user.pk:
            out[t.survey_id][1] += 1
    return {sid: tuple(v) for sid, v in out.items()}


def badge_counts_json(survey, user=None):
    """`open_counts` flattened to {"kind:key": n} for the client refresh."""
    counts = open_counts(survey, user)
    flat = {}
    for kind in ANCHOR_KINDS:
        for key, n in counts[kind].items():
            flat[f'{kind}:{key}'] = n
    return {'counts': flat, 'total': counts['total'], 'new': sorted(counts['new_keys']), 'new_total': counts['new_total']}


def mentionable_members(survey):
    """Everyone a comment may @mention: the members of the survey's workspace.

    Membership, not SurveyCollaborator — an org owner without a collaborator
    row still has the survey through the org baseline and must be reachable.
    """
    return (Membership.objects.filter(organization=survey.organization)
            .select_related('user').order_by('user__first_name', 'user__username'))


def participants_of(thread):
    """Creator + every author + everyone mentioned anywhere in the thread."""
    users = set()
    if thread.created_by_id and thread.created_by:
        users.add(thread.created_by)
    for c in thread.comments.filter(deleted_at__isnull=True).select_related('author').prefetch_related('mentions'):
        if c.author is not None:
            users.add(c.author)
        users.update(c.mentions.all())
    return users


def display_name(user):
    if user is None:
        return 'Someone'
    return user.get_full_name() or user.username


# ─── Writes ─────────────────────────────────────────────────────────────────

def _member_users(survey, user_ids):
    ids = {int(i) for i in user_ids if str(i).isdigit()}
    if not ids:
        return []
    return [m.user for m in mentionable_members(survey) if m.user_id in ids]


def validate_attachment(uploaded):
    if uploaded.size > MAX_ATTACHMENT_BYTES:
        raise AttachmentRejected(f'Files can be at most {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.')
    content_type = (uploaded.content_type or mimetypes.guess_type(uploaded.name or '')[0] or '').lower()
    if content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise AttachmentRejected('This file type is not allowed. Images, PDF, Office and text files are.')
    kind = 'image' if content_type.startswith('image/') else 'file'
    return kind, content_type


def attach(comment, files):
    if len(files) > MAX_ATTACHMENTS_PER_COMMENT:
        raise AttachmentRejected(f'At most {MAX_ATTACHMENTS_PER_COMMENT} files per comment.')
    checked = [(f,) + validate_attachment(f) for f in files]
    out = []
    for f, kind, content_type in checked:
        out.append(CommentAttachment.objects.create(
            comment=comment, kind=kind, file=f, original_name=(f.name or kind)[:255],
            content_type=content_type, size_bytes=f.size))
    return out


@transaction.atomic
def open_thread(survey, actor, kind, key, body, mention_ids=(), files=()):
    fields = anchor_fields(survey, kind, key)
    thread = CommentThread.objects.create(survey=canonical_of(survey), created_by=actor, **fields)
    comment = _post(thread, actor, body, mention_ids, files)
    return thread, comment


@transaction.atomic
def reply(thread, actor, body, mention_ids=(), files=()):
    return _post(thread, actor, body, mention_ids, files)


def _post(thread, actor, body, mention_ids, files):
    comment = Comment.objects.create(thread=thread, author=actor, body=body.strip())
    mentions = _member_users(thread.survey, mention_ids)
    if mentions:
        comment.mentions.set(mentions)
    if files:
        attach(comment, list(files))
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=['last_activity_at'])
    return comment


def resolve(thread, actor):
    thread.status = 'resolved'
    thread.resolved_by = actor
    thread.resolved_at = timezone.now()
    thread.last_activity_at = thread.resolved_at
    thread.save(update_fields=['status', 'resolved_by', 'resolved_at', 'last_activity_at'])
    return thread


def reopen(thread, actor):
    thread.status = 'open'
    thread.resolved_by = None
    thread.resolved_at = None
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=['status', 'resolved_by', 'resolved_at', 'last_activity_at'])
    return thread


@transaction.atomic
def delete_comment(comment):
    """Soft delete: the row stays so the thread reads coherently, the content goes."""
    for a in comment.attachments.all():
        a.file.delete(save=False)
        a.delete()
    comment.mentions.clear()
    comment.body = ''
    comment.deleted_at = timezone.now()
    comment.save(update_fields=['body', 'deleted_at'])
    return comment


def edit_comment(comment, body):
    comment.body = body.strip()
    comment.edited_at = timezone.now()
    comment.save(update_fields=['body', 'edited_at'])
    return comment


def can_edit(comment, user):
    return comment.author_id is not None and comment.author_id == user.pk and comment.deleted_at is None


def can_delete(comment, user, effective_role):
    return effective_role == 'owner' or (comment.author_id is not None and comment.author_id == user.pk)


# ─── Notifications ──────────────────────────────────────────────────────────

def notify(thread, comment, actor):
    """Queue one mail per participant except the actor, after commit."""
    from .tasks import send_thread_notification
    recipients = [u for u in participants_of(thread) if u.pk != getattr(actor, 'pk', None) and u.email]
    if not recipients:
        return []
    ids = sorted({u.pk for u in recipients})

    def _enqueue():
        for uid in ids:
            send_thread_notification.delay(thread.pk, comment.pk, getattr(actor, 'pk', None), uid)
    transaction.on_commit(_enqueue)
    return ids

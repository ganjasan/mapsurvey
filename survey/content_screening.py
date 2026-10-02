"""Phishing screening of creator-authored survey text (openspec: phishing-content-review).

Registration defenses (`survey/abuse.py`) stop bots; this module is for the
human with a throwaway mailbox who publishes an "XFINITY — click here to
proceed" page on our domain. The rules, in the order they matter:

* The scorer is a pure function. `collect_text()` reads the survey once,
  `score()` has no database or network access, and the signal table below is
  the ONE place a new incident becomes a rule.
* Nothing is banned automatically. A survey at or above the threshold is HELD
  (`ContentReview(status='pending')` — respondents get a neutral page) and the
  owner decides from the review mail: `release()` or `confirm_phishing()`.
* Screening fails OPEN. `screen_survey()` swallows every exception: a scorer
  bug must never block a creator's publish.
* The creator is told the survey is under review and nothing else — listing
  the signals to the person who tripped them is how such filters get mapped.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

HOLD_TRIGGERS = ('publish', 'draft_publish', 'live_edit')
MAX_TEXT_BYTES = 200 * 1024
EXCERPT_CHARS = 120
REVIEW_TOKEN_SALT = 'survey.abuse_review'
REVIEW_TOKEN_MAX_AGE = 14 * 24 * 3600

# --- signal table ------------------------------------------------------------
# weight per hit, cap per signal. Calibrated on the 2026-10-02 scan of 582
# surveys: the two incidents score 19 and 8, the highest legitimate survey 5,
# threshold 7 (settings.CONTENT_SCREENING_HOLD_THRESHOLD).
WEIGHTS = {
    'shortener': (4, 8),
    'tracker': (2, 2),
    'external_link': (2, 2),
    'brand': (2, 4),
    'lure': (1, 4),
    'padding': (3, 3),
    'single_question': (1, 1),
    'fresh_account': (2, 2),
    'disposable_domain': (2, 2),
}

SHORTENER_HOSTS = {
    'bit.ly', 'bitly.com', 'tinyurl.com', 't.co', 'cutt.ly', 'is.gd', 'rb.gy', 't.ly', 's.id',
    'rebrand.ly', 'shorturl.at', 'tiny.cc', 'ow.ly', 'buff.ly', 'bl.ink', 'goo.gl', 'qrco.de',
    'xaply.in', 'short.io', 'tiny.one', 'v.gd', 'u.to', 'clck.ru', 'surl.li', 'lnk.bio',
}
# A host that is only a redirect hop: `go.`/`link.`/`lnk.` on an apex nobody
# would read as a brand, or a bare 2-level host on a cheap TLD with a short path.
SHORTENER_HOST_RE = re.compile(r'^(go|link|lnk|l|s|u|r)\.[^.]+\.[a-z]{2,}$', re.I)
TRACKER_HOST_RE = re.compile(
    r'(^|\.)(zohoinsights\.com|list-manage\.com|sendgrid\.net|mandrillapp\.com|mailchi\.mp|'
    r'hubspotlinks\.com|constantcontact\.com|getresponse\.com|klclick\d*\.com)$'
    r'|^(click|clicks|trk|track|tracking|links|email|mail|sender\d*)\.', re.I)
TRACKER_PATH_RE = re.compile(r'/(ck\d*|ls/click|track/click|wf/click|e3t)/', re.I)

ALWAYS_SAFE_HOSTS = (
    'mapsurvey.org', 'google.com', 'google.co.uk', 'google.de', 'googleusercontent.com',
    'youtube.com', 'youtu.be', 'vimeo.com', 'wikipedia.org', 'wikimedia.org',
    'openstreetmap.org', 'osm.org', 'maps.app.goo.gl', 'github.com', 'gov.uk',
)
SAFE_SUFFIX_RE = re.compile(r'\.(gov|edu|mil)$|\.(gov|edu|ac)\.[a-z]{2}$', re.I)

BRAND_TERMS = (
    'xfinity', 'comcast', 'microsoft', 'office 365', 'office365', 'outlook', 'sharepoint',
    'onedrive', 'docusign', 'dropbox', 'paypal', 'wells fargo', 'chase bank', 'bank of america',
    'barclays', 'hsbc', 'lloyds', 'apple id', 'icloud', 'netflix', 'amazon prime', 'usps',
    'fedex', 'dhl', 'ups delivery', 'irs', 'hmrc', 'coinbase', 'binance', 'metamask',
    'adobe sign', 'webmail', 'everymail', 'roundcube', 'cpanel', 'godaddy', 'zimbra',
)
LURE_PHRASES = (
    'click here', 'proceed', 'verify your', 'confirm your', 'sign in', 'log in', 'login',
    'password', 'mailbox', 'almost set', "you're almost", 'account suspended', 'suspended',
    'pdf document', 'secure message', 'shared a file', 'shared a document', 'view document',
    'unlock', 'expire', 'update your', 'reactivate', 'validate your', 'security alert',
    'unusual activity', 'invoice attached', 'payment pending', 'gift card', 'seed phrase',
    'wallet', 'credit card number', 'card number', 'cvv', 'social security', 'ssn',
    'date of birth', 'mother\'s maiden',
)
# Built-in disposable-mail domains; `DISPOSABLE_EMAIL_DOMAINS` extends it.
DISPOSABLE_DOMAINS = {
    'betterr.org', 'mailinator.com', 'guerrillamail.com', 'guerrillamail.info', 'sharklasers.com',
    'grr.la', '10minutemail.com', '10minutemail.net', 'yopmail.com', 'yopmail.fr', 'tempmail.com',
    'temp-mail.org', 'temp-mail.io', 'tmpmail.net', 'tmpmail.org', 'getnada.com', 'nada.email',
    'maildrop.cc', 'dropmail.me', 'mohmal.com', 'emailondeck.com', 'fakeinbox.com', 'trashmail.com',
    'trashmail.de', 'dispostable.com', 'mintemail.com', 'throwawaymail.com', 'mailnesia.com',
    'tempr.email', 'discard.email', 'spamgourmet.com', 'mailcatch.com', 'inboxkitten.com',
    'burnermail.io', 'moakt.com', 'tempail.com', 'crazymailing.com', 'ellbit.com', 'mailsac.com',
    'mail7.io', 'tempmailo.com', 'emailfake.com', 'luxusmail.org', 'tmail.ws', 'mailpoof.com',
}

EMPTY_PARAGRAPH_RE = re.compile(r'<p[^>]*>(?:\s|&nbsp;|<br\s*/?>)*</p>', re.I)
PADDING_MIN = 20
LINK_RE = re.compile(r'(?:href\s*=\s*["\']?\s*|\b)(https?://[^\s"\'<>)]+)', re.I)
URL_IN_TEXT_RE = re.compile(r'\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s"\'<>)]*)?', re.I)


@dataclass
class ScreenInput:
    """Everything `score()` looks at, read once from the survey."""
    texts: list = field(default_factory=list)  # (label, raw html/text)
    redirect_url: str = ''
    question_count: int = 0
    account_age_hours: float | None = None
    email_domain: str = ''


@dataclass
class ScreenResult:
    score: int
    signals: list  # [{'key', 'weight', 'excerpt'}]
    fingerprint: str


# --- collection --------------------------------------------------------------

def collect_text(survey, now=None) -> ScreenInput:
    """Gather the creator-authored text of `survey` and the account facts.

    Survey name, section titles and subheadings (plus translations), question
    names and subtexts (plus translations), the thanks page in every language
    and `redirect_url`. Capped at MAX_TEXT_BYTES so a 10-language Formatted
    Text block cannot turn one publish into a regex marathon.
    """
    from .models import Question, QuestionTranslation, SurveySection, SurveySectionTranslation

    now = now or timezone.now()
    inp = ScreenInput()
    texts = [('name', survey.name or '')]
    sections = list(SurveySection.objects.filter(survey_header=survey).only('id', 'title', 'subheading'))
    section_ids = [s.id for s in sections]
    for s in sections:
        texts.append(('section.title', s.title or ''))
        texts.append(('section.subheading', s.subheading or ''))
    for t in SurveySectionTranslation.objects.filter(section_id__in=section_ids).only('title', 'subheading'):
        texts.append(('section.title', t.title or ''))
        texts.append(('section.subheading', t.subheading or ''))
    questions = list(Question.objects.filter(survey_section_id__in=section_ids).only('id', 'name', 'subtext'))
    for q in questions:
        texts.append(('question.name', q.name or ''))
        texts.append(('question.subtext', q.subtext or ''))
    for t in QuestionTranslation.objects.filter(question_id__in=[q.id for q in questions]).only('name', 'subtext'):
        texts.append(('question.name', t.name or ''))
        texts.append(('question.subtext', t.subtext or ''))
    thanks = survey.thanks_html or {}
    if isinstance(thanks, dict):
        for v in thanks.values():
            texts.append(('thanks', v or ''))
    elif thanks:
        texts.append(('thanks', str(thanks)))

    budget = MAX_TEXT_BYTES
    for label, text in texts:
        if budget <= 0:
            break
        piece = text[:budget]
        budget -= len(piece)
        if piece:
            inp.texts.append((label, piece))

    redirect = (survey.redirect_url or '').strip()
    inp.redirect_url = '' if redirect in ('', '#') else redirect
    inp.question_count = len(questions)

    user = survey.created_by
    if user is not None:
        if user.date_joined:
            inp.account_age_hours = max(0.0, (now - user.date_joined).total_seconds() / 3600)
        email = (user.email or '').strip().lower()
        inp.email_domain = email.rsplit('@', 1)[1] if '@' in email else ''
    return inp


# --- scoring -----------------------------------------------------------------

def _host_of(url: str) -> str:
    try:
        parsed = urlparse(url if '://' in url else 'http://' + url)
    except ValueError:
        return ''
    host = (parsed.hostname or '').lower().strip('.')
    return host[4:] if host.startswith('www.') else host


def _is_safe_host(host: str) -> bool:
    if not host:
        return True
    own = {_host_of(getattr(settings, 'SITE_URL', '') or ''), _host_of(getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or '')}
    own.discard('')
    for safe in list(ALWAYS_SAFE_HOSTS) + list(own):
        if host == safe or host.endswith('.' + safe):
            return True
    return bool(SAFE_SUFFIX_RE.search(host))


def _is_shortener(host: str) -> bool:
    if host in SHORTENER_HOSTS:
        return True
    for apex in SHORTENER_HOSTS:
        if host.endswith('.' + apex):
            return True
    return bool(SHORTENER_HOST_RE.match(host)) and not _is_safe_host(host)


def _is_tracker(url: str, host: str) -> bool:
    return bool(TRACKER_HOST_RE.search(host)) or bool(TRACKER_PATH_RE.search(urlparse(url if '://' in url else 'http://' + url).path or ''))


def _links_in(texts, redirect_url):
    """Every URL in the texts (href attributes and bare http links) + redirect."""
    seen = []
    for _label, text in texts:
        for m in LINK_RE.finditer(text):
            seen.append(m.group(1))
    if redirect_url:
        seen.append(redirect_url)
    out, known = [], set()
    for url in seen:
        url = url.rstrip('.,;:')
        if url not in known:
            known.add(url)
            out.append(url)
    return out


def _excerpt(text: str, needle: str = '') -> str:
    plain = ' '.join(strip_tags(text).split())
    if needle:
        idx = plain.lower().find(needle.lower())
        if idx >= 0:
            start = max(0, idx - 40)
            return plain[start:start + EXCERPT_CHARS]
    return plain[:EXCERPT_CHARS]


def _term_hits(plain_lower: str, terms, cap_hits: int):
    hits = []
    for term in terms:
        if re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', plain_lower):
            hits.append(term)
            if len(hits) >= cap_hits:
                break
    return hits


def score(inp: ScreenInput) -> ScreenResult:
    """Deterministic score + the signals that produced it. No I/O."""
    signals = []

    def add(key, excerpt='', hits=1):
        weight, cap = WEIGHTS[key]
        current = sum(s['weight'] for s in signals if s['key'] == key)
        gained = min(weight * hits, max(0, cap - current))
        if gained > 0:
            signals.append({'key': key, 'weight': gained, 'excerpt': excerpt[:EXCERPT_CHARS]})

    # Links: shorteners, trackers, anything external.
    external = []
    for url in _links_in(inp.texts, inp.redirect_url):
        host = _host_of(url)
        if not host or _is_safe_host(host):
            continue
        external.append(url)
        if _is_shortener(host):
            add('shortener', url)
        elif _is_tracker(url, host):
            add('tracker', url)
    if external:
        add('external_link', external[0])

    # Vocabulary over the tag-stripped text.
    plain = ' '.join(strip_tags(text) for _label, text in inp.texts)
    plain = ' '.join(plain.replace('&nbsp;', ' ').split()).lower()
    for term in _term_hits(plain, BRAND_TERMS, 2):
        add('brand', _excerpt(plain, term))
    for term in _term_hits(plain, LURE_PHRASES, 4):
        add('lure', _excerpt(plain, term))

    # Shape of the page.
    empties = sum(len(EMPTY_PARAGRAPH_RE.findall(text)) for _label, text in inp.texts)
    if empties >= PADDING_MIN:
        add('padding', f'{empties} empty paragraphs')
    if inp.question_count <= 1:
        add('single_question', f'{inp.question_count} question(s)')

    # Account facts.
    age = inp.account_age_hours
    if age is not None:
        if age < 1:
            add('fresh_account', f'registered {int(age * 60)} min before publishing')
        elif age < 24:
            weight, _cap = WEIGHTS['fresh_account']
            signals.append({'key': 'fresh_account', 'weight': max(1, weight - 1), 'excerpt': f'registered {age:.1f} h before publishing'})
    if inp.email_domain and inp.email_domain in disposable_domains():
        add('disposable_domain', inp.email_domain)

    total = sum(s['weight'] for s in signals)
    return ScreenResult(score=total, signals=signals, fingerprint=fingerprint(inp))


def disposable_domains():
    return DISPOSABLE_DOMAINS | set(getattr(settings, 'DISPOSABLE_EMAIL_DOMAINS', []) or [])


def fingerprint(inp: ScreenInput) -> str:
    """SHA-256 of the normalised screened text; account facts excluded on purpose
    — a cleared survey stays cleared as its author's account ages."""
    h = hashlib.sha256()
    for _label, text in inp.texts:
        h.update(' '.join(text.split()).encode('utf-8', 'replace'))
        h.update(b'\x00')
    h.update(inp.redirect_url.encode('utf-8', 'replace'))
    return h.hexdigest()


def hold_threshold() -> int:
    return int(getattr(settings, 'CONTENT_SCREENING_HOLD_THRESHOLD', 7))


# --- entry point -------------------------------------------------------------

def screen_survey(survey, *, trigger: str):
    """Score `survey`; hold it when the score reaches the threshold.

    Returns the ScreenResult, or None when screening is off or failed. Never
    raises — the callers are the publish paths and must complete regardless.
    """
    if not getattr(settings, 'CONTENT_SCREENING', True):
        return None
    try:
        return _screen(survey, trigger)
    except Exception:  # noqa: BLE001 — fail open, by design
        logger.exception('content screening failed for survey %s (%s)', getattr(survey, 'id', '?'), trigger)
        return None


def _screen(survey, trigger):
    from .models import ContentReview
    from .versioning import canonical_of

    canonical = canonical_of(survey)
    inp = collect_text(canonical)
    result = score(inp)
    if result.score < hold_threshold():
        return result

    reviews = ContentReview.objects.filter(survey=canonical)
    if reviews.filter(status='confirmed').exists():
        return result
    if reviews.filter(status='cleared', fingerprint=result.fingerprint).exists():
        return result

    open_review = reviews.filter(status__in=ContentReview.OPEN_STATUSES).order_by('-created_at').first()
    if open_review is not None:
        was_held = open_review.status == 'pending'
        open_review.status = 'pending'
        open_review.score = result.score
        open_review.signals = result.signals
        open_review.fingerprint = result.fingerprint
        open_review.trigger = trigger
        open_review.save(update_fields=['status', 'score', 'signals', 'fingerprint', 'trigger'])
        if not was_held:
            _log('content_screen', f'hold survey={canonical.id} score={result.score} trigger={trigger}')
            notify_owner(open_review)
        return result

    review = ContentReview.objects.create(
        survey=canonical, status='pending', source='screen', trigger=trigger,
        score=result.score, signals=result.signals, fingerprint=result.fingerprint,
    )
    _log('content_screen', f'hold survey={canonical.id} score={result.score} trigger={trigger}')
    notify_owner(review)
    return result


def is_held(survey) -> bool:
    """One indexed exists() — the respondent gate's whole cost."""
    from .models import ContentReview
    from .versioning import canonical_of
    return ContentReview.objects.filter(survey=canonical_of(survey), status='pending').exists()


def pending_review_for(survey):
    from .models import ContentReview
    from .versioning import canonical_of
    return ContentReview.objects.filter(survey=canonical_of(survey), status='pending').first()


# --- respondent reports -------------------------------------------------------

REPORT_REASONS = (
    ('phishing', 'Asks for a password, a login or a payment'),
    ('scam', 'Looks like a scam or impersonates a company'),
    ('other', 'Something else'),
)


def report(survey, reason, message, request):
    """A respondent flagged the survey. Opens a `reported` review (no hold) and
    mails the owner once; later reports on the same open review only count.
    Returns (review, created)."""
    from .abuse import log_abuse_event
    from .models import ContentReview
    from .versioning import canonical_of

    canonical = canonical_of(survey)
    note_line = f'{reason}: {(message or "").strip()[:500]}'.rstrip(': ')
    open_review = ContentReview.objects.filter(
        survey=canonical, status__in=ContentReview.OPEN_STATUSES).order_by('-created_at').first()
    if open_review is not None:
        open_review.report_count += 1
        open_review.note = (open_review.note + '\n' + note_line).strip()
        open_review.save(update_fields=['report_count', 'note'])
        log_abuse_event('content_screen', request, f'report survey={canonical.id} reason={reason} repeat')
        return open_review, False

    try:
        fp = fingerprint(collect_text(canonical))
    except Exception:  # noqa: BLE001 — the report matters more than the fingerprint
        fp = ''
    review = ContentReview.objects.create(
        survey=canonical, status='reported', source='report', report_count=1, note=note_line, fingerprint=fp,
    )
    log_abuse_event('content_screen', request, f'report survey={canonical.id} reason={reason}')
    notify_owner(review)
    return review, True


# --- decisions ----------------------------------------------------------------

def release(review, actor, request=None):
    """Owner says the survey is fine. Respondents see it on the next request."""
    if not review.is_open:
        return False
    review.status = 'cleared'
    review.decided_by = actor
    review.decided_at = timezone.now()
    review.save(update_fields=['status', 'decided_by', 'decided_at'])
    _log('content_screen', f'release survey={review.survey_id} review={review.id}', request)
    return True


def confirm_phishing(review, actor, request=None):
    """Owner confirms. Deactivate the account, close every survey it created,
    end its login sessions, record everything. Reversible from the admin."""
    from django.contrib.sessions.models import Session

    from .models import AuditLog, SurveyHeader

    if not review.is_open:
        return False
    survey = review.survey
    user = survey.created_by
    closed = []
    targets = SurveyHeader.objects.filter(status__in=('draft', 'testing', 'published'))
    targets = targets.filter(created_by=user) if user is not None else targets.filter(pk=survey.pk)
    for s in targets:
        s.status = 'closed'
        s.save(update_fields=['status'])
        closed.append(s.id)
        try:
            AuditLog.objects.create(
                actor=actor, action='content_screen_close', survey_uuid=s.uuid, survey_name=s.name,
                ip=_ip(request), metadata={'review': review.id, 'user': user.id if user else None},
            )
        except Exception:  # noqa: BLE001 — audit must not undo the decision
            logger.exception('audit row failed for survey %s', s.id)

    if user is not None:
        user.is_active = False
        user.save(update_fields=['is_active'])
        uid = str(user.id)
        for sess in Session.objects.filter(expire_date__gte=timezone.now()).iterator():
            try:
                if str(sess.get_decoded().get('_auth_user_id')) == uid:
                    sess.delete()
            except Exception:  # noqa: BLE001 — a corrupt session is not worth a 500
                continue

    review.status = 'confirmed'
    review.decided_by = actor
    review.decided_at = timezone.now()
    review.note = (review.note + f'\nclosed surveys: {closed}').strip()
    review.save(update_fields=['status', 'decided_by', 'decided_at', 'note'])
    _log('content_screen', f'confirm survey={survey.id} user={user.id if user else "none"} review={review.id}', request)
    return True


# --- owner notice -------------------------------------------------------------

def review_token(review) -> str:
    return signing.dumps({'r': review.id}, salt=REVIEW_TOKEN_SALT, compress=True)


def review_from_token(token: str):
    """The review a mail link points at, or None for a bad or stale token."""
    from .models import ContentReview
    try:
        data = signing.loads(token, salt=REVIEW_TOKEN_SALT, max_age=REVIEW_TOKEN_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    return ContentReview.objects.select_related('survey', 'survey__created_by', 'decided_by').filter(pk=data.get('r')).first()


def review_path(review) -> str:
    from django.urls import reverse
    return reverse('abuse_review', kwargs={'token': review_token(review)})


def notice_context(review) -> dict:
    """What the mail and the review page both show."""
    from .mail import absolute_url
    from .models import ContentReview, SurveyHeader, SurveySession

    survey = review.survey
    user = survey.created_by
    account = None
    if user is not None:
        email = (user.email or '').lower()
        account = {
            'username': user.username,
            'email_domain': email.rsplit('@', 1)[1] if '@' in email else '',
            'joined': user.date_joined,
            'is_active': user.is_active,
            'surveys': SurveyHeader.objects.filter(created_by=user).count(),
            'sessions': SurveySession.objects.filter(survey__created_by=user).count(),
            'prior_reviews': list(
                ContentReview.objects.filter(survey__created_by=user).exclude(pk=review.pk)
                .values('id', 'status', 'score', 'created_at')
            ),
        }
    return {
        'review': review,
        'survey': survey,
        'survey_url': absolute_url(f'/surveys/{survey.uuid}/'),
        'editor_url': absolute_url(f'/editor/surveys/{survey.uuid}/'),
        'review_url': absolute_url(review_path(review)),
        'signals': review.signals or [],
        'account': account,
        'reason_label': dict(REPORT_REASONS).get((review.note or '').split(':', 1)[0], ''),
    }


def notice_subject(review) -> str:
    if review.source == 'report':
        return f'[Mapsurvey] Survey reported by a respondent: {review.survey.name}'
    return f'[Mapsurvey] Survey held for review: {review.survey.name} (score {review.score})'


def send_notice(review, fail_silently=False):
    from .mail import send_templated_mail
    return send_templated_mail(
        'abuse/review_notice', settings.ABUSE_REVIEW_EMAIL, notice_subject(review),
        notice_context(review), fail_silently=fail_silently,
    )


def notify_owner(review):
    """Enqueue the notice; if the broker is unreachable send it right here.
    A held survey with no mail is the one state this feature must not produce."""
    from .tasks import send_abuse_review_notice
    try:
        send_abuse_review_notice.delay(review.id)
    except Exception:  # noqa: BLE001 — broker down: send inline
        logger.exception('could not enqueue review notice %s; sending inline', review.id)
        try:
            send_notice(review, fail_silently=True)
        except Exception:  # noqa: BLE001
            logger.exception('inline review notice %s failed', review.id)


# --- small helpers ------------------------------------------------------------

def _ip(request):
    if request is None:
        return None
    from .abuse import client_ip
    return client_ip(request) or None


def _log(defense, detail, request=None):
    from .abuse import log_abuse_event, log_abuse_event_noreq
    if request is not None:
        log_abuse_event(defense, request, detail)
    else:
        log_abuse_event_noreq(defense, detail)

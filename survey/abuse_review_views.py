"""Owner review of a held or reported survey, and the respondent report form.

The review link travels by email, and mail clients prefetch links, so GET is
read-only and staff-gated (404 for everyone else — the page must not even
confirm a token exists) and both decisions are CSRF-protected POSTs. See
openspec/changes/phishing-content-review/design.md (D6, D8).
"""
import logging

from django import forms
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_ratelimit.core import get_usage, is_ratelimited

from . import content_screening as cs
from .access_control import check_survey_access

logger = logging.getLogger(__name__)

REPORT_LIMIT = '3/h'


@require_http_methods(['GET', 'POST'])
def abuse_review(request, token):
    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    review = cs.review_from_token(token)
    if review is None:
        raise Http404

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if review.is_open and action == 'release':
            cs.release(review, request.user, request)
        elif review.is_open and action == 'confirm':
            cs.confirm_phishing(review, request.user, request)
        # A decided review accepts nothing; re-render shows the decision.
        return redirect('abuse_review', token=token)

    context = cs.notice_context(review)
    context.update({
        'decided': not review.is_open,
        'held': review.status == 'pending',
        'status_label': review.get_status_display(),
    })
    return render(request, 'abuse/review.html', context)


class ReportForm(forms.Form):
    reason = forms.ChoiceField(choices=cs.REPORT_REASONS, widget=forms.RadioSelect)
    message = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={'rows': 3}),
                              label=_('Anything else we should know? (optional)'))


@require_http_methods(['GET', 'POST'])
def survey_report(request, survey_slug):
    """A respondent flags the survey. Never changes what respondents see."""
    from .views import resolve_survey

    survey = resolve_survey(survey_slug)
    # Same visibility rules as the survey itself: a draft stays a 404, a
    # closed survey still shows the closed page — nothing new is revealed.
    if survey.status != 'published':
        blocked = check_survey_access(request, survey)  # draft → 404, closed → closed page
        if blocked is not None:
            return blocked

    if request.method == 'POST':
        if _report_limited(request):
            return HttpResponse(_('Too many reports from this connection. Please try again later.'),
                                status=429, headers={'Retry-After': '3600'})
        form = ReportForm(request.POST)
        if form.is_valid():
            _report_count(request)
            cs.report(survey, form.cleaned_data['reason'], form.cleaned_data['message'], request)
            return render(request, 'abuse/report_done.html', {'survey': survey})
    else:
        form = ReportForm()
    return render(request, 'abuse/report.html', {'survey': survey, 'form': form})


def _report_limited(request):
    """Budget already spent? Read-only, fail-open (same reasoning as registration)."""
    try:
        usage = get_usage(request, group='survey_report', fn=None, key='survey.abuse.ratelimit_key',
                          rate=REPORT_LIMIT, method='POST', increment=False)
    except Exception:  # noqa: BLE001 — cache outage must not block a report
        return False
    return bool(usage) and usage['count'] >= usage['limit']


def _report_count(request):
    try:
        is_ratelimited(request=request, group='survey_report', fn=None, key='survey.abuse.ratelimit_key',
                       rate=REPORT_LIMIT, method='POST', increment=True)
    except Exception:  # noqa: BLE001
        pass

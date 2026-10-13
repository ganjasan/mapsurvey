"""Views for `/demo/` — the two-step "Request a demo" form (change request-demo-form)."""
from datetime import timedelta

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import demo_request as dr
from .abuse import (
    HONEYPOT_FIELD_NAME,
    check_limits,
    demo_request_limits,
    increment_limits,
    log_abuse_event,
)
from .models import DemoRequest


def _render(request, state, **ctx):
    ctx.update({'state': state, 'honeypot_name': HONEYPOT_FIELD_NAME})
    return render(request, 'demo.html', ctx)


def _rate_limited(request, retry_after):
    resp = render(
        request,
        'registration/rate_limited.html',
        {'retry_after_minutes': max(1, round(retry_after / 60))},
        status=429,
    )
    resp['Retry-After'] = str(retry_after)
    return resp


@require_http_methods(['GET', 'POST'])
def demo_request(request):
    """Step one: an email, nothing else. Submitting it creates the lead."""
    source = dr.normalise_source(request.POST.get('src') if request.method == 'POST' else request.GET.get('src'))

    if request.method == 'POST':
        # Honeypot first, from raw POST: a bot gets the same redirect a person
        # gets, to a step-two URL that matches no row and renders "done".
        if request.POST.get(HONEYPOT_FIELD_NAME, '').strip():
            log_abuse_event('honeypot', request, 'demo_request')
            return redirect(reverse('demo_request_done'))

        limits = demo_request_limits()
        hit = check_limits(request, limits)
        if hit:
            retry_after, detail = hit
            log_abuse_event('ratelimit', request, detail)
            return _rate_limited(request, retry_after)

        form = dr.DemoEmailForm(request.POST)
        if form.is_valid():
            increment_limits(request, limits)
            row = DemoRequest.objects.create(
                email=form.cleaned_data['email'],
                source=source,
                user=request.user if request.user.is_authenticated else None,
            )
            dr.notify(row, 'email')
            dr.emit(request, row, 'email')
            return redirect(reverse('demo_request_details', args=[row.key]), permanent=False)
    else:
        initial = {}
        if request.user.is_authenticated and request.user.email:
            initial['email'] = request.user.email
        form = dr.DemoEmailForm(initial=initial)

    return _render(request, 'email', form=form, source=source)


@require_http_methods(['GET', 'POST'])
def demo_request_details(request, key):
    """Step two: the details, on the row step one created. Skippable."""
    row = DemoRequest.objects.filter(key=key).first()
    if row is None:
        raise Http404
    closed = (
        row.details_at is not None
        or row.created_at < timezone.now() - timedelta(days=dr.DETAILS_WINDOW_DAYS)
    )
    if closed or request.GET.get('skip'):
        return _render(request, 'done')

    if request.method == 'POST':
        if request.POST.get(HONEYPOT_FIELD_NAME, '').strip():
            log_abuse_event('honeypot', request, 'demo_request_details')
            return _render(request, 'done')
        form = dr.DemoDetailsForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            row.name = data.get('name', '')
            row.organisation = data.get('organisation', '')
            row.project = data.get('project', '')
            row.timeline = data.get('timeline', '')
            row.details_at = timezone.now()
            row.save(update_fields=['name', 'organisation', 'project', 'timeline', 'details_at'])
            dr.notify(row, 'details')
            dr.emit(request, row, 'details')
            return _render(request, 'done')
    else:
        form = dr.DemoDetailsForm()
    return _render(request, 'details', form=form, row=row)


def demo_request_done(request):
    """The page a honeypot hit lands on. Looks exactly like success."""
    return _render(request, 'done')

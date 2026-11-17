"""How much a report is read (change reports-usage-api, #710).

Counted on our server — the public page loads no third-party analytics — as one row per report,
day and kind: `view` (the page opened), `embed` (the page or one block opened inside another
site), `pdf` (the stored PDF downloaded). No visitor is identified or stored; a request by a
signed-in member of the report's workspace is the author looking at their own work and is not
counted. A count that fails never breaks the page.
"""
import logging

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

log = logging.getLogger('reports.usage')

KINDS = ('view', 'embed', 'pdf')


def _is_member(request, report):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    from survey.permissions import get_org_membership
    return get_org_membership(user, report.organization) is not None


def count(request, report, kind):
    """Add one to today's counter of `kind`, unless the visitor is a member of the workspace."""
    from reports.models import ReportUsage
    if kind not in KINDS or request.method != 'GET':
        return
    try:
        if _is_member(request, report):
            return
        day = timezone.localdate()
        updated = ReportUsage.objects.filter(report=report, day=day, kind=kind).update(count=F('count') + 1)
        if not updated:
            try:
                with transaction.atomic():
                    ReportUsage.objects.create(report=report, day=day, kind=kind, count=1)
            except IntegrityError:      # another request made the row first
                ReportUsage.objects.filter(report=report, day=day, kind=kind).update(count=F('count') + 1)
    except Exception:  # noqa: BLE001 — a number for the author is never worth a reader's page
        log.warning('report usage: count failed', exc_info=True)


def summary(report, days=30):
    """{'view': {'total', 'recent'}, 'embed': …, 'pdf': …, 'days': 30, 'since': first day counted}."""
    from reports.models import ReportUsage
    since = timezone.localdate() - timezone.timedelta(days=days - 1)
    out = {kind: {'total': 0, 'recent': 0} for kind in KINDS}
    rows = ReportUsage.objects.filter(report=report)
    for row in rows.values('kind').annotate(n=Sum('count')):
        if row['kind'] in out:
            out[row['kind']]['total'] = row['n'] or 0
    for row in rows.filter(day__gte=since).values('kind').annotate(n=Sum('count')):
        if row['kind'] in out:
            out[row['kind']]['recent'] = row['n'] or 0
    first = rows.order_by('day').values_list('day', flat=True).first()
    out.update(days=days, since=first)
    return out

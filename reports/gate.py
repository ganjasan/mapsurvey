"""Reports is a Pro module (change reports-pro, #709; owner decision 2026-11-16).

Three questions, one place:

- ``covered(org)`` — the feature is in force for the workspace: its plan includes it, or a live
  Pro trial does. A covered workspace's reports stay live and editable.
- ``use(org, user)`` — a member is about to WRITE (create a report, change a block, publish).
  True when covered; for a workspace that never had a trial this write starts it
  (`billing.trial.use`), as the first Pro use anywhere does; False when neither applies — the
  caller answers with the upgrade page.
- ``freeze_if_lapsed(report)`` — a published report of a workspace that is NOT covered is served
  as a frozen snapshot, taken the first time it is asked for after the cover ended. Readers keep
  the link, nothing is deleted, never a 404; the author edits again on Pro. The same rule serves
  the day the module replaced the free public results page and the day a subscription lapses.

The public page never refuses for the plan; only writes do.
"""
from billing import entitlements as ents
from billing import trial

FEATURE = 'reports'


def covered(organization):
    return organization is not None and ents.for_organization(organization).covers(FEATURE)


def may_write(organization):
    """Whether a write would be let through (covered, or it would start the trial) — for showing
    the editor as editable. Asks, never starts."""
    return covered(organization) or trial.startable(organization, FEATURE)


def use(organization, user=None):
    """Let one write through, starting the workspace's trial if this is its first Pro use."""
    if covered(organization):
        return True
    if not trial.startable(organization, FEATURE):
        return False
    return bool(trial.use(organization, FEATURE, actor=user))


def freeze_if_lapsed(report):
    """Freeze a published live report of a workspace without cover, as of now. Returns True when
    it froze one. Idempotent: a frozen report is left alone."""
    if not report.is_published or report.mode == 'frozen' or covered(report.organization):
        return False
    from reports.render import freeze_report
    freeze_report(report)
    return True


def lapsed_reports(organization=None):
    """Published live reports of workspaces without cover — what `freeze_if_lapsed` would freeze
    on their next view. For the ship-day count and the management command."""
    from reports.models import Report
    reports = Report.objects.filter(is_published=True).exclude(mode='frozen').select_related('organization', 'survey')
    if organization is not None:
        reports = reports.filter(organization=organization)
    return [r for r in reports if not covered(r.organization)]

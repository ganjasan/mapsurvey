#!/usr/bin/env python
"""Google Search Console report for the Monday growth review.

Pulls Search-Analytics data for the mapsurvey.org property via a service
account (read-only) and prints:
  1. site-wide top queries (clicks / impressions / CTR / avg position)
  2. per-query performance of the /for-educators/ page
  3. top pages by impressions

Setup (one-time, already done 2026-07-05):
  - GCP service account with the Search Console API enabled
  - its client_email added in GSC -> Settings -> Users and permissions (Restricted)
  - JSON key stored OUTSIDE the repo (never commit it)

Usage:
  python scripts/gsc_report.py                 # last 7 days
  python scripts/gsc_report.py --days 28
  python scripts/gsc_report.py --page /for-educators/ --days 28
  GSC_KEY=/path/to/key.json python scripts/gsc_report.py

Authentication is shared with `survey.acquisition`, which the funnel dashboard's
sync command uses, so this report and the dashboard can never disagree about which
property or credential they read.

Data note: GSC data lags ~2 days and starts accumulating only after the
property was verified (2026-07-04) — early runs will legitimately be empty.
"""
import argparse
import datetime as dt
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mapsurvey.settings")
django.setup()

from survey.acquisition import (  # noqa: E402
    GSC_LAG_DAYS, NotConfigured, ProviderError, gsc_service,
)


def service():
    """The shared client, or a readable exit if the credential is missing/broken."""
    try:
        return gsc_service()
    except (NotConfigured, ProviderError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


def query(svc, site, days, dimensions, page_filter=None, limit=25):
    end = dt.date.today() - dt.timedelta(days=GSC_LAG_DAYS)
    start = end - dt.timedelta(days=days)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": dimensions,
        "rowLimit": limit,
    }
    if page_filter:
        body["dimensionFilterGroups"] = [{
            "filters": [{"dimension": "page", "operator": "contains", "expression": page_filter}]
        }]
    resp = svc.searchanalytics().query(siteUrl=site, body=body).execute()
    return resp.get("rows", [])


def show(title, rows, key_label):
    print(f"\n== {title} ==")
    if not rows:
        print("  (no data — property is young or nothing ranked in this window)")
        return
    print(f"  {key_label:55s} {'clicks':>6} {'impr':>7} {'ctr':>6} {'pos':>6}")
    for r in rows:
        key = " / ".join(r.get("keys", ["?"]))[:55]
        print(f"  {key:55s} {r['clicks']:>6.0f} {r['impressions']:>7.0f} "
              f"{r['ctr'] * 100:>5.1f}% {r['position']:>6.1f}")


def main():
    ap = argparse.ArgumentParser(description="GSC report for mapsurvey.org")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--page", default="/for-educators/")
    args = ap.parse_args()

    svc, site = service()

    # Access check: the property must be visible to the service account.
    sites = [s["siteUrl"] for s in svc.sites().list().execute().get("siteEntry", [])]
    if site not in sites:
        print(f"ERROR: {site} is not accessible to this service account.")
        print(f"  Accessible: {sites or 'none'}")
        print("  Fix: GSC -> Settings -> Users and permissions -> add the service-account email.")
        sys.exit(1)
    print(f"Property OK: {site} (window: last {args.days} days, data lags ~2 days)")

    show("Top queries — site-wide", query(svc, site, args.days, ["query"]), "query")
    show(f"Queries for {args.page}",
         query(svc, site, args.days, ["query"], page_filter=args.page), "query")
    show("Top pages", query(svc, site, args.days, ["page"]), "page")


if __name__ == "__main__":
    main()

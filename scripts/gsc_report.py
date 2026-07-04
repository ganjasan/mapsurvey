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

Data note: GSC data lags ~2 days and starts accumulating only after the
property was verified (2026-07-04) — early runs will legitimately be empty.
"""
import argparse
import datetime as dt
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

DEFAULT_KEY = os.path.expanduser("~/.config/mapsurvey/konuchovlab-897862dc8046.json")
KEY_PATH = os.environ.get("GSC_KEY", DEFAULT_KEY)
SITE = os.environ.get("GSC_SITE", "sc-domain:mapsurvey.org")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def service():
    creds = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def query(svc, days, dimensions, page_filter=None, limit=25):
    end = dt.date.today() - dt.timedelta(days=2)   # GSC data lags ~2 days
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
    resp = svc.searchanalytics().query(siteUrl=SITE, body=body).execute()
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

    svc = service()

    # Access check: the property must be visible to the service account.
    sites = [s["siteUrl"] for s in svc.sites().list().execute().get("siteEntry", [])]
    if SITE not in sites:
        print(f"ERROR: {SITE} is not accessible to this service account.")
        print(f"  Accessible: {sites or 'none'}")
        print("  Fix: GSC -> Settings -> Users and permissions -> add the service-account email.")
        sys.exit(1)
    print(f"Property OK: {SITE} (window: last {args.days} days, data lags ~2 days)")

    show("Top queries — site-wide", query(svc, args.days, ["query"]), "query")
    show(f"Queries for {args.page}", query(svc, args.days, ["query"], page_filter=args.page),
         "query")
    show("Top pages", query(svc, args.days, ["page"]), "page")


if __name__ == "__main__":
    main()

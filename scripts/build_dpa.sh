#!/bin/bash
# Rebuild the DPA draft from its HTML source.
#
# This document is NOT published. It lives in legal/ rather than
# survey/assets/ specifically so that `collectstatic` cannot put it back on the
# public site: the previous version was a PDF with no source, and it kept
# telling institutional buyers that we host in Frankfurt long after we did not.
# It was withdrawn from /trust/ on 2026-08-15 pending legal review -- see
# legal/mapsurvey-dpa.html for the open questions.
#
# Do not re-link it from a template until a lawyer has been through it.

set -e

cd "$(dirname "$0")/.."

SRC="legal/mapsurvey-dpa.html"
OUT="legal/mapsurvey-dpa.pdf"

command -v weasyprint >/dev/null || {
    echo "weasyprint not found. Install it: pipx install weasyprint" >&2
    exit 1
}

weasyprint "$SRC" "$OUT"
echo "✓ $OUT (draft — not published)"

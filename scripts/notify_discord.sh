#!/usr/bin/env bash
# Post a message to the Mapsurvey Discord channel via an Incoming Webhook.
#
# Usage:
#   scripts/notify_discord.sh "Plain message text"
#   scripts/notify_discord.sh --title "Release v1.2" --color 5763719 "Body of the update..."
#   git log --oneline -5 | scripts/notify_discord.sh --title "Recent commits" --stdin
#
# Options:
#   --title TEXT      Render as a rich embed with this title (otherwise a plain message).
#   --color N         Embed color as a decimal integer (e.g. 5763719 = Discord blurple).
#   --username NAME   Override the webhook's display name for this message.
#   --stdin           Read the message body from stdin (handy for piping changelogs).
#   -h, --help        Show this help.
#
# Webhook URL resolution (first hit wins):
#   1. $DISCORD_WEBHOOK_URL environment variable  (use this in CI / GitHub Actions secrets)
#   2. DISCORD_WEBHOOK_URL from a local .env file
#
# Exit codes: 0 ok, 1 usage error, 2 missing webhook, 3 HTTP failure.
set -euo pipefail

TITLE=""
COLOR=""
USERNAME=""
READ_STDIN=0
MSG=""

usage() {
  grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'
  exit "${1:-1}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)    TITLE="$2"; shift 2 ;;
    --color)    COLOR="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --stdin)    READ_STDIN=1; shift ;;
    -h|--help)  usage 0 ;;
    --)         shift; MSG="$*"; break ;;
    -*)         echo "Unknown option: $1" >&2; usage 1 ;;
    *)          MSG="$*"; break ;;
  esac
done

if [[ "$READ_STDIN" -eq 1 ]]; then
  MSG="$(cat)"
fi

if [[ -z "$MSG" ]]; then
  echo "Error: no message provided." >&2
  usage 1
fi

# Resolve the webhook URL: env var first, then a DISCORD_WEBHOOK_URL line in .env.
if [[ -z "${DISCORD_WEBHOOK_URL:-}" && -f .env ]]; then
  DISCORD_WEBHOOK_URL="$(grep -E '^DISCORD_WEBHOOK_URL=' .env | tail -1 | cut -d= -f2- || true)"
  # Strip optional surrounding quotes / whitespace.
  DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL%\"}"; DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL#\"}"
  DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL//[$'\t\r\n ']/}"
fi
if [[ -z "${DISCORD_WEBHOOK_URL:-}" ]]; then
  echo "Error: DISCORD_WEBHOOK_URL is not set (checked env and .env)." >&2
  exit 2
fi

# Build the JSON payload with python3 — robust escaping, unicode, and length limits.
PAYLOAD="$(TITLE="$TITLE" COLOR="$COLOR" USERNAME="$USERNAME" MSG="$MSG" python3 - <<'PY'
import json, os

msg = os.environ["MSG"]
title = os.environ.get("TITLE", "")
color = os.environ.get("COLOR", "")
username = os.environ.get("USERNAME", "")

payload = {}
if username:
    payload["username"] = username

if title:
    # Embeds: title <=256, description <=4096.
    embed = {"title": title[:256], "description": msg[:4096]}
    if color:
        embed["color"] = int(color)
    payload["embeds"] = [embed]
else:
    # Plain content is capped at 2000 chars.
    payload["content"] = msg[:2000]

print(json.dumps(payload))
PY
)"

# POST it. Discord returns 204 (no body) on success, 200 when ?wait=true is used.
HTTP_CODE="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST -d "$PAYLOAD" "$DISCORD_WEBHOOK_URL")"

if [[ "$HTTP_CODE" != "204" && "$HTTP_CODE" != "200" ]]; then
  echo "Discord webhook returned HTTP $HTTP_CODE" >&2
  exit 3
fi
echo "Posted to Discord (HTTP $HTTP_CODE)."

#!/usr/bin/env python3
"""Is the authorization server reachable the way a connector reaches it?

ChatGPT and claude.ai fetch the discovery document, register a client and
exchange codes from their own egress ranges with short timeouts; a Cloudflare
challenge page or a slow answer on any of the three shows up as "could not
connect" in their dialogs with no further detail. This script asks the three
endpoints the way they do and fails on a non-JSON body or an answer slower
than the budget. Run it after the first deploy of change oauth-server and
after any Cloudflare change:

    python scripts/oauth_reachability_check.py https://mapsurvey.org

It issues nothing: the registration body is deliberately invalid (a JSON 400
proves the endpoint is ours, not a challenge page) and the token request names
a grant that cannot exist.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BUDGET_SECONDS = 10.0
UA = 'mapsurvey-oauth-reachability/1'


def fetch(method, url, body=None, content_type=None):
    data = body.encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={'User-Agent': UA, 'Accept': 'application/json'})
    if content_type:
        req.add_header('Content-Type', content_type)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=BUDGET_SECONDS) as response:
            status, raw, ctype = response.status, response.read(), response.headers.get('Content-Type', '')
    except urllib.error.HTTPError as err:
        status, raw, ctype = err.code, err.read(), err.headers.get('Content-Type', '')
    elapsed = time.monotonic() - started
    return status, raw, ctype, elapsed


def check(name, method, url, body=None, content_type=None, expect_status=None):
    status, raw, ctype, elapsed = fetch(method, url, body, content_type)
    problems = []
    if elapsed > BUDGET_SECONDS:
        problems.append(f'{elapsed:.1f}s > {BUDGET_SECONDS}s')
    if 'json' not in ctype:
        problems.append(f'Content-Type {ctype!r} (a challenge page?)')
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = None
        problems.append('body is not JSON')
    if expect_status and status not in expect_status:
        problems.append(f'status {status}, expected one of {expect_status}')
    verdict = 'ok' if not problems else 'FAIL'
    print(f'{verdict:4} {name:12} {status} {elapsed:5.2f}s {url}' + (f'  -- {"; ".join(problems)}' if problems else ''))
    return payload, not problems


def main(origin):
    origin = origin.rstrip('/')
    ok = True
    meta, good = check('discovery', 'GET', origin + '/.well-known/oauth-authorization-server', expect_status=(200,))
    ok &= good
    if meta:
        for key in ('issuer', 'authorization_endpoint', 'token_endpoint', 'registration_endpoint'):
            if key not in meta:
                print(f'FAIL discovery  missing {key}')
                ok = False
        if meta.get('code_challenge_methods_supported') != ['S256']:
            print('FAIL discovery  code_challenge_methods_supported is not ["S256"]')
            ok = False
    # Probe the ORIGIN given, not the document's URLs: on a dev server the
    # issuer is production (SITE_URL) and following it would poke the live site.
    # A document whose endpoints live elsewhere is reported, not followed.
    for key in ('authorization_endpoint', 'token_endpoint', 'registration_endpoint'):
        value = (meta or {}).get(key, '')
        if value and not value.startswith(origin + '/'):
            print(f'note discovery  {key} is {value} (not under {origin}; expected on a dev server)')
    register_url = origin + '/oauth/register/'
    token_url = origin + '/oauth/token/'
    _, good = check('register', 'POST', register_url, body='{"redirect_uris": "not-a-list"}',
                    content_type='application/json', expect_status=(400,))
    ok &= good
    _, good = check('token', 'POST', token_url,
                    body='grant_type=authorization_code&code=none&client_id=none&redirect_uri=https%3A%2F%2Fnone.invalid%2F&code_verifier=none',
                    content_type='application/x-www-form-urlencoded', expect_status=(400, 401))
    ok &= good
    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

#!/usr/bin/env python3
"""Turn a settings document into a Mapbox GL style and publish it to the Mapsurvey account.

Usage:
    python scripts/mapbox_style_publish.py scripts/map_styles/paper_a.json
    python scripts/mapbox_style_publish.py scripts/map_styles/paper_a.json --dry-run --out /tmp/a.json
    python scripts/mapbox_style_publish.py scripts/map_styles/paper_a.json --base-file survey/tests/fixtures/mapbox_streets_v12.json

Change map-styles-rendering-path (#541, epic #545). Paper A and Paper B were built by hand
over `streets-v12` on 2026-11-06; this is that work as code, so a style is a settings
document rather than a thing that lives in Mapbox Studio. The generator and the Styles API
client live in `survey/map_styles/generator.py` (change map-styles-library, #542) and are
shared with the app's publishing task; this file is the command line around them. The token
is `MAPBOX_STYLES_TOKEN` from the environment or the repo's `.env` (a secret token with
styles:read, styles:write, styles:list) — never the public one, and nothing here is ever
rendered into a page.

A style is named after its settings' `name`; a second run with the same name updates the
existing style (`PATCH`) instead of creating another. A name held by two styles stops the
run. The settings keys are documented in the generator module.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from survey.map_styles.generator import (  # noqa: E402
    DEFAULT_BASE, MapboxApiError, MapboxStylesClient, apply_settings, publish,
)


def load_token():
    token = os.environ.get('MAPBOX_STYLES_TOKEN', '')
    if token:
        return token
    try:
        from dotenv import dotenv_values
    except ImportError:  # pragma: no cover
        return ''
    return dotenv_values(os.path.join(REPO, '.env')).get('MAPBOX_STYLES_TOKEN', '') or ''


def _client(account):
    try:
        return MapboxStylesClient(load_token(), account)
    except ValueError as error:
        raise SystemExit(f'{error}; put it in the environment or in .env') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('settings', help='settings JSON file')
    parser.add_argument('--account', default=os.environ.get('MAPBOX_ACCOUNT', 'artemkonuchov'))
    parser.add_argument('--base-file', help='use this style JSON as the base instead of fetching it')
    parser.add_argument('--dry-run', action='store_true', help='build the style, publish nothing')
    parser.add_argument('--out', help='write the built style JSON here')
    parser.add_argument('--check', default='12.57,55.68,13',
                        help='lng,lat,zoom of the Static Images check frame printed after publishing')
    args = parser.parse_args(argv)

    with open(args.settings) as handle:
        settings = json.load(handle)
    base = None
    if args.base_file:
        with open(args.base_file) as handle:
            base = json.load(handle)

    try:
        if args.dry_run:
            if base is None:
                base = _client(args.account).get_style(settings.get('base', DEFAULT_BASE))
            style = apply_settings(base, settings)
            _write(style, args.out)
            print(f'dry run: {len(style["layers"])} layers, nothing published')
            return 0

        client = _client(args.account)
        style_id, action = publish(settings, client, base=base)
        if args.out:
            _write(apply_settings(base or client.get_style(settings.get('base', DEFAULT_BASE)), settings), args.out)
    except (MapboxApiError, ValueError) as error:
        raise SystemExit(str(error)) from None
    lng, lat, zoom = args.check.split(',')
    print(f'{action}: {args.account}/{style_id}')
    print(f'check frame: {client.static_url(style_id, lng, lat, zoom)}')
    return 0


def _write(style, path):
    if path:
        with open(path, 'w') as handle:
            json.dump(style, handle, indent=1, sort_keys=True)
    else:
        json.dump(style, sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write('\n')


if __name__ == '__main__':
    sys.exit(main())

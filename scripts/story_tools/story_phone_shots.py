"""Phone-sized screenshots (390x844 @2x) of local survey pages.

Usage: shoot_phone.py <locale> [click=<link text>] name=url ...
Steps run in order; `click=` clicks a link/button by text on the current page (language choice).
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / 'shots' / 'phone'
OUT.mkdir(parents=True, exist_ok=True)
HIDE_TOOLBAR = "document.querySelectorAll('#djDebug').forEach(e => e.remove())"

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True,
                              has_touch=True, locale=sys.argv[1])
    page = ctx.new_page()
    for arg in sys.argv[2:]:
        key, value = arg.split('=', 1)
        if key == 'click':
            page.evaluate(HIDE_TOOLBAR)
            page.get_by_text(value, exact=True).first.click()
            page.wait_for_load_state('networkidle')
            continue
        if key == 'js':
            page.evaluate(value)
            time.sleep(1.5)
            continue
        if key == 'goto':
            page.goto(value, wait_until='networkidle')
            continue
        if value != 'shot':
            page.goto(value, wait_until='networkidle')
            time.sleep(2.5)
        page.evaluate(HIDE_TOOLBAR)
        page.screenshot(path=str(OUT / f'{key}.png'))
        print('saved', key, page.url)
    browser.close()

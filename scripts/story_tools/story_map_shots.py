"""Screenshot every maps/*.html at exact pixel size with headless Chromium (Playwright)."""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / 'shots'
OUT.mkdir(exist_ok=True)
names = sys.argv[1:] or sorted(p.stem for p in (HERE / 'maps').glob('*.html'))

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={'width': 1040, 'height': 800}, device_scale_factor=2)
    page = ctx.new_page()
    for name in names:
        page.goto(f'http://localhost:8421/{name}.html', wait_until='networkidle')
        page.wait_for_function('window.__ready === true')
        time.sleep(2.5)  # tiles fade in
        page.locator('#map').screenshot(path=str(OUT / f'{name}.png'))
        print('saved', OUT / f'{name}.png')
    browser.close()

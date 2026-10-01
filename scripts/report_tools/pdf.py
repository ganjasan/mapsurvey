"""HTML → PDF for survey reports (skill survey-report).

    python scripts/report_tools/pdf.py report.html report.pdf              # A4 pages, for print
    python scripts/report_tools/pdf.py report.html report-long.pdf --single --width 1100
                                                    # one tall page, exactly as on screen

The single-page form is what customers asked for on 2026-10-01: no page breaks cutting a map,
screen styles kept. Chromium's limit is about 5 m of page; the reports so far are 1.8–3 m.
"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def html_to_pdf(src, dst, single=False, width=1100, footer=None):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': width if single else 794, 'height': 1123})
        page.goto(Path(src).resolve().as_uri(), wait_until='networkidle')
        time.sleep(1.2)
        if single:
            page.emulate_media(media='screen')
            height = page.evaluate('Math.ceil(document.documentElement.scrollHeight)')
            page.pdf(path=str(dst), width=f'{width}px', height=f'{height + 2}px', print_background=True,
                     margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'}, page_ranges='1')
        else:
            page.emulate_media(media='print')
            opts = dict(format='A4', print_background=True,
                        margin={'top': '12mm', 'bottom': '14mm', 'left': '10mm', 'right': '10mm'})
            if footer:
                opts.update(display_header_footer=True, header_template='<span></span>',
                            footer_template=f'<div style="font-size:8px;width:100%;text-align:center;color:#8A94A8">{footer} · <span class="pageNumber"></span>/<span class="totalPages"></span></div>')
            page.pdf(path=str(dst), **opts)
        browser.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--single', action='store_true'); ap.add_argument('--width', type=int, default=1100)
    ap.add_argument('--footer')
    a = ap.parse_args()
    html_to_pdf(a.src, a.dst, a.single, a.width, a.footer)

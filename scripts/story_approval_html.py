#!/usr/bin/env python3
"""Build the self-contained "story for approval" page a customer signs off before publication.

    python scripts/story_approval_html.py <slug> <approval.json> <out.html>

Reads `survey/story_data/<slug>/` (story.json, body.html, images/) — the same files
`seed_story` installs, so what the customer approves is what goes online — and embeds every
picture as a data URI, so the one HTML file opens from an email attachment on any machine.

`approval.json` holds what is NOT in the story: the review frame and the asks.

    {
      "reviewer": "the City of Olney",              # "For review by …"
      "headline": "The White Squirrel Count on mapsurvey.org",
      "intro": ["<p>…</p>", "<p>…</p>"],            # paragraphs under the headline (HTML)
      "legend": "new since your last review",       # optional; omit on a first review
      "card_note": "New: the card uses …",          # optional note under the homepage card
      "questions": ["<b>Your name.</b> …", "…"],     # numbered asks, HTML
      "thanks": "Thank you for your work on the count.",
      "signature": "Artem Konuchov, Mapsurvey",
      "new": ["route-map", "own-words"]             # optional: ids of <h2 id=…> to tag "new"
    }

Marking text as new: in body.html wrap a paragraph in `<div class="new">…</div>` or add
`<span class="tag">new</span>` inside a heading/figcaption — both are styled here and are
harmless on the live site (no such CSS there, so they render as plain text; strip them before
the final seed). Run from the repo root.
"""
import base64
import json
import mimetypes
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = """
:root{--text:#1B2A4A;--text2:#5A6680;--text3:#8A94A8;--accent:#0FA58E;--bg:#F7F5F0;--bg-warm:#EFECE5;--card:#fff;--border:#D4CFC6;--border-light:#E4E0D8;--hl:#FFF3C4;--hl-border:#E8B93A;--display:'Instrument Sans',system-ui,sans-serif;--serif:'Source Serif 4',Georgia,serif;--mono:'JetBrains Mono',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--serif);line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}@media(min-width:720px){.wrap{padding:0 32px}}
.intro{background:var(--text);color:#F7F5F0;padding:40px 0 36px}.intro .kicker{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#8FE3D4;margin-bottom:10px}
.intro h1{font-family:var(--display);font-size:clamp(1.6rem,3.5vw,2.2rem);line-height:1.2;letter-spacing:-.02em;margin-bottom:14px}.intro p{font-size:1.05rem;color:#C9D2E3;max-width:720px;margin-bottom:10px}
.intro .legend{display:inline-flex;gap:10px;align-items:center;margin-top:8px;font-family:var(--display);font-size:.9rem;color:#F7F5F0}.intro .legend span{background:var(--hl);color:var(--text);border-left:3px solid var(--hl-border);padding:2px 10px;border-radius:3px}
.part{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--text3);margin:48px 0 16px;padding-bottom:10px;border-bottom:1px solid var(--border-light)}.part b{color:var(--text);font-weight:500}
.where{font-family:var(--display);font-size:.95rem;color:var(--text2);margin:-4px 0 20px}
.new{background:var(--hl);border-left:3px solid var(--hl-border);padding:6px 12px;margin-left:-15px;border-radius:0 4px 4px 0}
h2 .tag,figcaption .tag{font-family:var(--mono);font-size:10px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;background:var(--hl-border);color:var(--text);padding:3px 7px;border-radius:10px;vertical-align:4px;margin-left:8px}figcaption .tag{vertical-align:1px;margin-left:6px}
.home-block{background:var(--bg-warm);border:1px solid var(--border-light);border-radius:14px;padding:28px}.home-block .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:6px}.home-block .block-title{font-family:var(--display);font-size:1.3rem;letter-spacing:-.01em;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--border-light);border-radius:12px;overflow:hidden;max-width:400px;box-shadow:0 2px 8px rgba(27,42,74,.06)}.card .cover{position:relative;aspect-ratio:16/9;background:#dfe6ef}.card .cover img{width:100%;height:100%;object-fit:cover;display:block}.card .type{position:absolute;top:10px;left:10px;font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;background:rgba(255,255,255,.92);padding:4px 8px;border-radius:4px}
.card .body{padding:16px 18px 18px}.card .place{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text3);margin-bottom:6px}.card h4{font-family:var(--display);font-size:1.1rem;line-height:1.3;margin-bottom:8px}.card .body>p{font-size:.95rem;color:var(--text2);margin-bottom:12px}
.card .chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}.card .chips span{font-family:var(--display);font-size:.78rem;background:var(--bg-warm);border:1px solid var(--border-light);padding:3px 9px;border-radius:12px}
.card .foot{display:flex;justify-content:space-between;align-items:center;font-family:var(--display);font-size:.82rem;color:var(--text2)}.card .foot img{height:18px;vertical-align:middle;margin-right:6px}.card .more{color:var(--accent);font-weight:600}
.story{background:var(--card);border:1px solid var(--border-light);border-radius:14px;padding:32px 24px 40px;margin-top:8px}@media(min-width:720px){.story{padding:48px 64px 56px}}
.story .crumbs{font-family:var(--display);font-size:.82rem;color:var(--text3);margin-bottom:24px}.story>.place{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
.story h1{font-family:var(--display);font-size:clamp(1.7rem,4vw,2.5rem);line-height:1.15;letter-spacing:-.02em;margin-bottom:16px;max-width:720px}.story .lead{font-size:1.2rem;color:var(--text2);max-width:720px;margin-bottom:24px}
.byline{display:flex;flex-wrap:wrap;gap:16px 28px;align-items:center;font-family:var(--display);font-size:.9rem;color:var(--text2);padding:16px 0;border-top:1px solid var(--border-light);border-bottom:1px solid var(--border-light);margin-bottom:28px}.byline .org{display:inline-flex;align-items:center;gap:10px;color:var(--text);font-weight:600}.byline .org img{height:36px}.byline .org small{display:block;font-weight:400;color:var(--text2);font-size:.82rem}
figure.hero{margin:0 0 28px}figure.hero img{width:100%;border-radius:10px;display:block}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:36px}.facts div{background:var(--bg-warm);border-radius:10px;padding:14px 16px;font-family:var(--display);font-size:.85rem;color:var(--text2)}.facts b{display:block;font-size:1.5rem;color:var(--text);letter-spacing:-.02em;margin-bottom:2px}
.text{max-width:720px}.text h2{font-family:var(--display);font-size:1.45rem;letter-spacing:-.01em;margin:36px 0 12px}.text p{margin-bottom:14px;font-size:1.05rem}
.text figure,.text .sd-figure{margin:22px 0 26px}.text figure img{width:100%;border-radius:8px;display:block}.text figcaption{font-family:var(--display);font-size:.85rem;color:var(--text3);margin-top:8px}
.text .sd-figure--poster img,.text .sd-figure--photo img{max-width:480px;margin:0 auto}
blockquote,.sd-quote{border-left:3px solid var(--accent);padding:4px 0 4px 20px;margin:18px 0 22px;color:var(--text)}blockquote p{font-style:italic}blockquote cite{display:block;font-family:var(--display);font-size:.85rem;color:var(--text3);font-style:normal;margin-top:6px}
.sd-phones{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin:22px 0 26px}@media(min-width:720px){.sd-phones{grid-template-columns:repeat(4,1fr)}}.sd-phone{margin:0}.sd-phone__frame{border:6px solid #1B2A4A;border-radius:22px;overflow:hidden;background:#000}.sd-phone__frame img{display:block;width:100%;border-radius:0}.sd-phone figcaption{text-align:center}
.sd-legend{display:flex;flex-wrap:wrap;gap:14px;font-family:var(--display);font-size:.85rem;color:var(--text2);margin-top:8px}.sd-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.cta{margin-top:44px;background:var(--bg-warm);border-radius:12px;padding:28px;max-width:720px}.cta h2{font-family:var(--display);font-size:1.25rem;margin-bottom:8px}.cta p{color:var(--text2);margin-bottom:16px}.cta .btn{display:inline-block;background:var(--accent);color:#fff;font-family:var(--display);font-weight:600;padding:10px 18px;border-radius:8px}
.questions{background:var(--card);border:1px solid var(--border-light);border-radius:14px;padding:32px 24px;margin-bottom:64px}@media(min-width:720px){.questions{padding:40px 64px}}.questions h2{font-family:var(--display);font-size:1.4rem;margin-bottom:8px}.questions>p{color:var(--text2);margin-bottom:18px}
.questions ol{padding-left:22px;max-width:720px}.questions li{margin-bottom:14px;font-size:1.02rem}.questions .sign{margin-top:28px;font-family:var(--display);color:var(--text2)}
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}: story for review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<header class="intro"><div class="wrap">
  <p class="kicker">For review by {reviewer}</p>
  <h1>{headline}</h1>
  {intro}
  {legend}
</div></header>
<main class="wrap">
  <p class="part"><b>1.</b> Homepage card</p>
  <p class="where">Shown on the mapsurvey.org homepage in a row of customer stories. The whole card links to the story below.</p>
  <div class="home-block">
    <p class="eyebrow">From the field</p>
    <h3 class="block-title">Used by cities, planners and town-planning societies</h3>
    <div class="card">
      <div class="cover"><img src="{card_img}" alt=""><span class="type">{type_label}</span></div>
      <div class="body">
        <p class="place">{place} · {sector}</p>
        <h4>{title}</h4>
        <p>{summary}</p>
        <div class="chips">{chips}</div>
        <div class="foot"><span class="org">{logo_small}{credit}</span><span class="more">Read the story →</span></div>
      </div>
    </div>
    {card_note}
  </div>

  <p class="part"><b>2.</b> Story page</p>
  <p class="where">mapsurvey.org/stories/{slug}/</p>
  <article class="story">
    <p class="crumbs">Home / Stories / {place_short}</p>
    <p class="place">{place} · {sector}</p>
    <h1>{title}</h1>
    <p class="lead">{summary}</p>
    <div class="byline">
      <span class="org">{logo}<span>{credit}<small>{credit_note}</small></span></span>
      <span>{type_label} · {month}</span>
    </div>
    <figure class="hero"><img src="{cover_img}" alt="{cover_alt}"><figcaption>{cover_credit}</figcaption></figure>
    <div class="facts">{facts}</div>
    <div class="text">{body}</div>
    <div class="cta">
      <h2>Planning a survey like this one?</h2>
      <p>This survey runs on Mapsurvey. Draw your layers, write your questions and share one link. Free to start.</p>
      <span class="btn">Create your map survey</span>
    </div>
  </article>

  <p class="part"><b>3.</b> What we need from you</p>
  <section class="questions">
    <h2>Please confirm, change or strike</h2>
    <p>A short reply to each point is plenty. Anything you say no to comes out.</p>
    <ol>{questions}</ol>
    <p class="sign">{thanks}<br>{signature}</p>
  </section>
</main>
</body>
</html>
"""


def data_uri(path):
    mime = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def main(slug, approval_path, out_path):
    base = ROOT / 'survey' / 'story_data' / slug
    meta = json.loads((base / 'story.json').read_text(encoding='utf-8'))
    body = (base / 'body.html').read_text(encoding='utf-8')
    approval = json.loads(Path(approval_path).read_text(encoding='utf-8'))
    images = {k: data_uri(base / 'images' / v) for k, v in (meta.get('images') or {}).items()}
    body = re.sub(r'\{img:([A-Za-z0-9_-]+)\}', lambda m: images.get(m.group(1), ''), body)
    for anchor in approval.get('new', []):
        body = body.replace(f'<h2 id="{anchor}">', f'<h2 id="{anchor}" class="is-new">', 1)
        body = re.sub(rf'(<h2 id="{anchor}"[^>]*>)(.*?)(</h2>)', r'\1\2 <span class="tag">new</span>\3', body, count=1)
    img = lambda key: data_uri(base / 'images' / meta[key]) if meta.get(key) else ''
    logo = img('credit_logo')
    stamp = meta.get('published_date')
    month = date.fromisoformat(stamp[:10]).strftime('%B %Y') if stamp else ''
    html = PAGE.format(
        css=CSS, slug=slug, title=meta['title'], summary=meta.get('summary', ''),
        place=meta.get('place', ''), place_short=meta.get('place', '').split(',')[0], sector=meta.get('sector', ''),
        type_label={'case-study': 'Case study'}.get(meta.get('story_type'), meta.get('story_type', '')),
        credit=meta.get('credit', ''), credit_note=meta.get('credit_note', ''),
        logo=f'<img src="{logo}" alt="">' if logo else '', logo_small=f'<img src="{logo}" alt="">' if logo else '',
        card_img=img('card_image') or img('cover'), cover_img=img('cover'), cover_alt=meta.get('cover_alt', ''),
        cover_credit=meta.get('cover_credit', ''), month=month,
        chips=''.join(f"<span>{f.get('chip') or f['value']}</span>" for f in meta.get('facts', [])),
        facts=''.join(f"<div><b>{f['value']}</b>{f['label']}</div>" for f in meta.get('facts', [])),
        body=body, reviewer=approval['reviewer'], headline=approval['headline'],
        intro=''.join(approval.get('intro', [])),
        legend=f'<div class="legend"><span>{approval["legend"]}</span></div>' if approval.get('legend') else '',
        card_note=f'<p style="margin-top:14px;font-family:var(--display);font-size:.82rem;color:var(--text3)">{approval["card_note"]}</p>' if approval.get('card_note') else '',
        questions=''.join(f'<li>{q}</li>' for q in approval['questions']),
        thanks=approval.get('thanks', 'Thank you.'), signature=approval.get('signature', 'Artem Konuchov, Mapsurvey'),
    )
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'wrote {out_path} ({Path(out_path).stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])

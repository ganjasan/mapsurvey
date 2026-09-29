#!/usr/bin/env python3
"""Build the data files of the "Cycling in Copenhagen" demo (change copenhagen-demo).

Run once, review the output, commit it. `manage.py seed_demo_survey` reads only what
this script writes and never touches the network.

    env/bin/python scripts/build_copenhagen_demo.py [bridges] [samples]

Writes into survey/demo_data/copenhagen_cycling/:
  layers/0.geojson           bridges as points, reserved _key/_title/_category properties
  layers/0/objects.json      card text, Wikipedia link, photo credit, one photo each
  layers/0/assets/<key>.jpg  Wikimedia Commons photos, 800 px wide
  samples.json               ~40 sample sessions (tag `sample` is added by the command)

Sources: bridge facts and coordinates from Wikidata, photos from Wikimedia Commons (credit
and licence stored per photo), junction coordinates from Nominatim, routes from the
FOSSGIS bike router (routing.openstreetmap.de). All three are OpenStreetMap-based services
with usage policies that ask for a descriptive User-Agent and low request rates.

`survey.json` next to these files is written by hand, not by this script.
"""
import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'survey' / 'demo_data' / 'copenhagen_cycling'
UA = {'User-Agent': 'mapsurvey-demo-builder/1.0 (konuchovartem@mapsurvey.org)'}
CYCLE = 'Cycle and foot bridge'
ROAD = 'Road bridge with cycle lanes'

# key, Wikidata id, category, card text. Facts in the text are the Wikidata ones
# (opening year, length); nothing here should be stronger than that.
BRIDGES = [
    ('cykelslangen', 'Q60537471', CYCLE,
     'The Cycle Snake: a bikes-only ramp that winds above the harbourfront between Dybbølsbro '
     'and Bryggebroen, so riders skip the stairs. Opened in 2014, about 220 m long.'),
    ('bryggebroen', 'Q2927205', CYCLE,
     'Cycle and foot bridge between Islands Brygge and Vesterbro. Opened in 2006, about 190 m long.'),
    ('inderhavnsbroen', 'Q11977027', CYCLE,
     'Cycle and foot bridge between Nyhavn and Christianshavn. Its two halves slide apart to let '
     'ships through. Opened in 2016, about 180 m long.'),
    ('cirkelbroen', 'Q11963844', CYCLE,
     'Five circular platforms across the mouth of Christianshavn Canal, designed by Olafur Eliasson. '
     'Opened in 2015.'),
    ('lille-langebro', 'Q55748850', CYCLE,
     'Cycle and foot swing bridge beside Langebro, between the city centre and Christianshavn. '
     'Opened in 2019, about 175 m long.'),
    ('dronning-louises-bro', 'Q3428996', ROAD,
     'The bridge across the Lakes between the city centre and Nørrebro, from 1887. Wide cycle '
     'tracks carry some of the heaviest bike traffic in the city.'),
    ('abuen', 'Q21337230', CYCLE,
     'Åbuen, the arch on the Nørrebro cycle route that takes riders over Ågade without a crossing. '
     'Opened in 2008, about 65 m long.'),
    ('teglvaerksbroen', 'Q3076002', ROAD,
     'Bridge across Teglværkshavnen in Sydhavnen, opened in 2011, with cycle paths on both sides.'),
    ('knippelsbro', 'Q491808', ROAD,
     'Bascule road bridge from 1937 between the city centre and Christianshavn, with cycle lanes '
     'in both directions.'),
    ('langebro', 'Q944453', ROAD,
     'Bascule road bridge from 1954 between the city centre and Islands Brygge, with cycle lanes '
     'in both directions.'),
]

# Busy junctions for the unsafe-spot samples: Nominatim query, likely problems (choice codes
# of CPHSPWHY: 1 cars, 2 blind corner, 3 crowded, 4 surface, 5 confusing).
HOTSPOTS = [
    ('Rådhuspladsen, København', [1, 5, 3]),
    ('Nørreport Station, København', [3, 5]),
    ('Kongens Nytorv, København', [1, 5, 4]),
    ('Christianshavns Torv, København', [1, 2, 3]),
    ('Vesterbrogade 1, København', [1, 3]),
    ('Nørrebros Runddel, København', [1, 5]),
    ('H.C. Andersens Boulevard, København', [1, 3]),
    ('Dybbølsbro, København', [5, 2]),
    ('Østerport Station, København', [2, 5]),
    ('Enghave Plads, København', [2, 4]),
]

# Route endpoints (Nominatim queries); routes are rider-realistic pairs.
PLACES = {
    'norrebro': 'Nørrebroparken, København',
    'norreport': 'Nørreport Station, København',
    'islands': 'Islands Brygge 10, København',
    'kbhh': 'København H',
    'christianshavn': 'Christianshavns Torv, København',
    'frederiksberg': 'Frederiksberg Rådhus',
    'osterbro': 'Trianglen, København',
    'vesterbro': 'Enghave Plads, København',
    'amager': 'Amagerbro Station, København',
    'nyhavn': 'Nyhavn 1, København',
    'refshaleoen': 'Refshaleøen, København',
    'sydhavn': 'Sydhavn Station, København',
    'fisketorvet': 'Fisketorvet, København',
}
ROUTES = [
    ('norrebro', 'norreport'), ('islands', 'kbhh'), ('christianshavn', 'nyhavn'),
    ('frederiksberg', 'norreport'), ('osterbro', 'kbhh'), ('vesterbro', 'islands'),
    ('amager', 'christianshavn'), ('refshaleoen', 'nyhavn'), ('sydhavn', 'fisketorvet'),
    ('norrebro', 'christianshavn'), ('frederiksberg', 'islands'), ('osterbro', 'nyhavn'),
]

BRIDGE_UP = {
    'cykelslangen': .9, 'bryggebroen': .85, 'inderhavnsbroen': .8, 'cirkelbroen': .6,
    'lille-langebro': .9, 'dronning-louises-bro': .6, 'abuen': .85, 'teglvaerksbroen': .7,
    'knippelsbro': .45, 'langebro': .45,
}
BRIDGE_NOTES = {
    'cykelslangen': ['Best way to cross, no stairs', 'Gets slippery when it rains',
                     'Too narrow to overtake', 'Love the view over the harbour'],
    'bryggebroen': ['Wider lanes please, rush hour is tight', 'My daily commute, works well',
                    'Pedestrians walk in the bike lane', 'Needs better lighting at night'],
    'inderhavnsbroen': ['Too many tourists stopping in the lane', 'Great shortcut to Nyhavn',
                        'The slope on the Christianshavn side is steep'],
    'cirkelbroen': ['Tight turns with a bike trailer', 'Beautiful, but slow', 'Not built for commuting'],
    'lille-langebro': ['Finally a calm way across', 'Signs at the city end are confusing',
                       'Opens for boats at the worst times'],
    'dronning-louises-bro': ['Packed at 8 am', 'Cars turning right cut across the cycle track',
                             'Great in summer evenings'],
    'abuen': ['Smooth and quick', 'Needs lighting at night', 'Best part of the Nørrebro route'],
    'teglvaerksbroen': ['Fine, but the junction after it is messy', 'Quiet and easy'],
    'knippelsbro': ['Heavy traffic next to the cycle lane', 'Lane too narrow when it is busy',
                    'Exhaust fumes at rush hour'],
    'langebro': ['Cars too close', 'I take Lille Langebro instead', 'Loud and stressful'],
}
SPOT_NOTES = {
    1: ['Cars turn right across the cycle track', 'Buses pull out without looking'],
    2: ['You cannot see bikes coming round the corner'],
    3: ['Queues of bikes block the crossing at rush hour'],
    4: ['Cobbles and potholes'],
    5: ['Nobody knows who has right of way here', 'Lanes end suddenly'],
}
OTHER_NOTES = ['Same experience here', 'Happens every morning', 'Worse in winter', 'Agree, I avoid it',
               'Almost got hit here last week', 'Fine outside rush hour']


def _get(url, data=None):
    req = urllib.request.Request(url, headers=UA, data=data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _json(url):
    return json.loads(_get(url))


def geocode(query):
    time.sleep(1.1)  # Nominatim policy: at most one request per second
    hits = _json('https://nominatim.openstreetmap.org/search?format=json&limit=1&q='
                 + urllib.parse.quote(query))
    if not hits:
        raise SystemExit(f'Nominatim found nothing for {query!r}')
    return round(float(hits[0]['lon']), 6), round(float(hits[0]['lat']), 6)


def bike_route(a, b):
    time.sleep(1.0)
    url = ('https://routing.openstreetmap.de/routed-bike/route/v1/driving/'
           f'{a[0]},{a[1]};{b[0]},{b[1]}?overview=simplified&geometries=geojson')
    coords = _json(url)['routes'][0]['geometry']['coordinates']
    return [[round(x, 6), round(y, 6)] for x, y in coords]


def commons_photo(filename, key, assets):
    info = _json('https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo'
                 '&iiprop=url|extmetadata&iiurlwidth=800&titles=File:' + urllib.parse.quote(filename))
    page = next(iter(info['query']['pages'].values()))
    ii = page['imageinfo'][0]
    meta = ii.get('extmetadata', {})
    artist = _strip_html(meta.get('Artist', {}).get('value', 'Unknown author'))
    licence = meta.get('LicenseShortName', {}).get('value', '')
    (assets / f'{key}.jpg').write_bytes(_recompress(_get(ii['thumburl'])))
    return {'author': artist, 'licence': licence, 'page': ii['descriptionurl']}


def _recompress(data):
    """≤ 800 px JPEG at quality 72 keeps each card photo near 80 KB in the repository."""
    import io
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert('RGB')
    image.thumbnail((800, 800))
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=72, optimize=True, progressive=True)
    return out.getvalue()


def _strip_html(text):
    import re
    return re.sub(r'<[^>]+>', '', text).strip()[:120]


def build_bridges():
    assets = OUT / 'layers' / '0' / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    features, objects = [], []
    for key, qid, category, text in BRIDGES:
        entity = _json(f'https://www.wikidata.org/wiki/Special:EntityData/{qid}.json')['entities'][qid]
        claims = entity['claims']
        coord = claims['P625'][0]['mainsnak']['datavalue']['value']
        title = entity['labels'].get('da', entity['labels'].get('en'))['value']
        enwiki = entity.get('sitelinks', {}).get('enwiki', {}).get('title')
        link = (f'https://en.wikipedia.org/wiki/{urllib.parse.quote(enwiki.replace(" ", "_"))}'
                if enwiki else f'https://www.wikidata.org/wiki/{qid}')
        credit = commons_photo(claims['P18'][0]['mainsnak']['datavalue']['value'], key, assets)
        description = (f'<p>{text}</p><p><em>Photo: {credit["author"]}, {credit["licence"]}, '
                       f'<a href="{credit["page"]}">Wikimedia Commons</a>. '
                       'Location: OpenStreetMap contributors / Wikidata.</em></p>')
        features.append({'type': 'Feature',
                         'geometry': {'type': 'Point', 'coordinates': [round(coord['longitude'], 6),
                                                                       round(coord['latitude'], 6)]},
                         'properties': {'_key': key, '_title': title, '_category': category}})
        objects.append({'key': key, 'title': title, 'category': category, 'description': description,
                        'link': link, 'properties': {'wikidata': qid},
                        'assets': [{'kind': 'image', 'title': title, 'position': 0,
                                    'file': f'layers/0/assets/{key}.jpg', 'content_type': 'image/jpeg'}]})
        print(f'  bridge {title}: photo by {credit["author"]} ({credit["licence"]})')
    (OUT / 'layers' / '0.geojson').write_text(
        json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, indent=1))
    (OUT / 'layers' / '0' / 'objects.json').write_text(json.dumps(objects, ensure_ascii=False, indent=1))


def build_samples(n=40):
    rng = random.Random(20261001)
    hotspots = [(geocode(q), probs) for q, probs in HOTSPOTS]
    places = {k: geocode(q) for k, q in PLACES.items()}
    routes = [bike_route(places[a], places[b]) for a, b in ROUTES]
    unused_bridge_notes = {k: rng.sample(v, len(v)) for k, v in BRIDGE_NOTES.items()}
    sessions = []
    for i in range(n):
        freq = rng.choices([1, 2, 3], weights=[60, 25, 15])[0]
        s = {'days_ago': round(rng.uniform(0.5, 30), 2), 'freq': freq,
             'use': sorted(rng.sample([1, 2, 3, 4, 5], rng.choice([1, 1, 2, 3]))) if freq < 3 else [],
             'barriers': sorted(rng.sample([1, 2, 3, 4], rng.choice([1, 2]))) if freq == 3 else [],
             'safe': rng.choices([1, 2, 3, 4, 5], weights=[4, 12, 30, 38, 16])[0],
             'bridges': [], 'spots': [], 'route': None, 'reactions': []}
        for key in rng.sample(list(BRIDGE_UP), rng.randint(2, 5)):
            up = rng.random() < BRIDGE_UP[key]
            # Each sample comment appears once per bridge: a card that repeats itself
            # reads as fake, which is the one thing sample data must not do.
            note = unused_bridge_notes[key].pop() if unused_bridge_notes[key] and rng.random() < .2 else ''
            s['bridges'].append({'key': key, 'up': up, 'note': note})
        if rng.random() < .65:
            for _ in range(1 if rng.random() < .8 else 2):
                (lon, lat), probs = rng.choice(hotspots)
                why = rng.choice(probs)
                s['spots'].append({'lonlat': [round(lon + rng.uniform(-.0006, .0006), 6),
                                              round(lat + rng.uniform(-.0004, .0004), 6)],
                                   'why': why,
                                   'note': rng.choice(SPOT_NOTES[why]) if rng.random() < .35 else ''})
        if rng.random() < .7:
            s['route'] = {'coords': rng.choice(routes), 'rate': rng.choices([2, 3, 4, 5], weights=[10, 30, 40, 20])[0]}
        earlier = [(j, k) for j, prev in enumerate(sessions) for k in range(len(prev['spots']))]
        for j, k in rng.sample(earlier, min(len(earlier), rng.randint(0, 3))):
            note = ''
            if rng.random() < .15:
                used = {r['note'] for prev in sessions for r in prev['reactions']
                        if (r['session'], r['spot']) == (j, k)}
                fresh = [t for t in OTHER_NOTES if t not in used]
                note = rng.choice(fresh) if fresh else ''
            s['reactions'].append({'session': j, 'spot': k, 'up': rng.random() < .8, 'note': note})
        sessions.append(s)
    (OUT / 'samples.json').write_text(json.dumps({'sessions': sessions}, ensure_ascii=False, indent=1))
    print(f'  {n} sample sessions, {sum(len(s["spots"]) for s in sessions)} spots, '
          f'{sum(1 for s in sessions if s["route"])} routes')


if __name__ == '__main__':
    import sys
    parts = sys.argv[1:] or ['bridges', 'samples']
    if 'bridges' in parts:
        print('Bridges (Wikidata + Commons)…')
        build_bridges()
    if 'samples' in parts:
        print('Samples (Nominatim + bike routing)…')
        build_samples()

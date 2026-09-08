#!/usr/bin/env python3
"""Build the marker icon catalog and the Maki/Temaki sprites from upstream metadata.

Usage:
    python scripts/build_icon_catalog.py --fa <font-awesome-repo-or-metadata-dir> \
        --maki <mapbox/maki checkout> --temaki <rapideditor/temaki checkout> \
        [--fa-version 5.15.4] [--dump-terms <file>]

Inputs are NOT vendored. Download Font Awesome Free's `metadata/icons.json` and
`metadata/categories.yml` for the version the base templates load, clone Maki and
Temaki, run this, and commit what it writes:

    survey/assets/data/icon_catalog.json   — what the editor picker reads
    survey/assets/img/maki.svg             — <symbol> sheet, ids `maki-<name>`
    survey/assets/img/temaki.svg           — <symbol> sheet, ids `temaki-<name>`

Search terms for the non-English product languages come from the per-term tables under
`scripts/icon_terms/<lang>/*.json` ({"english term": "synonym synonym ..."}). A term with
no entry contributes only its English form, so a missing translation degrades to
English rather than hiding the icon. `scripts/icon_terms/extra_en.json` adds civic
vocabulary per icon value ("bus stop" on the bus). `--dump-terms` writes the unique English term list
those tables are keyed by, one per line, which is how the tables were first authored.

The script refuses to write an empty set and prints per-set counts so a shrunken catalog
is visible in review.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CATALOG_PATH = os.path.join(REPO, "survey", "assets", "data", "icon_catalog.json")
SPRITE_DIR = os.path.join(REPO, "survey", "assets", "img")
TERMS_DIR = os.path.join(HERE, "icon_terms")

LANGS = ["en", "ru", "de", "es", "fr", "pt", "pl", "id"]

# Product categories, in the order the picker shows them. `map` is the whole Maki +
# Temaki set; every other id is a theme an icon from any set can belong to.
CATEGORIES = [
    ("map", {"en": "Map", "ru": "Карта", "de": "Karte", "es": "Mapa", "fr": "Carte",
             "pt": "Mapa", "pl": "Mapa", "id": "Peta"}),
    ("transport", {"en": "Transport", "ru": "Транспорт", "de": "Verkehr", "es": "Transporte",
                   "fr": "Transport", "pt": "Transporte", "pl": "Transport", "id": "Transportasi"}),
    ("nature", {"en": "Nature", "ru": "Природа", "de": "Natur", "es": "Naturaleza",
                "fr": "Nature", "pt": "Natureza", "pl": "Przyroda", "id": "Alam"}),
    ("buildings", {"en": "Buildings", "ru": "Здания", "de": "Gebäude", "es": "Edificios",
                   "fr": "Bâtiments", "pt": "Edifícios", "pl": "Budynki", "id": "Bangunan"}),
    ("amenities", {"en": "Amenities", "ru": "Инфраструктура", "de": "Einrichtungen",
                   "es": "Servicios", "fr": "Équipements", "pt": "Serviços", "pl": "Udogodnienia",
                   "id": "Fasilitas"}),
    ("people", {"en": "People", "ru": "Люди", "de": "Menschen", "es": "Personas", "fr": "Personnes",
                "pt": "Pessoas", "pl": "Ludzie", "id": "Orang"}),
    ("safety", {"en": "Safety & problems", "ru": "Безопасность и проблемы",
                "de": "Sicherheit & Probleme", "es": "Seguridad y problemas",
                "fr": "Sécurité et problèmes", "pt": "Segurança e problemas",
                "pl": "Bezpieczeństwo i problemy", "id": "Keselamatan & masalah"}),
    ("health", {"en": "Health", "ru": "Здоровье", "de": "Gesundheit", "es": "Salud", "fr": "Santé",
                "pt": "Saúde", "pl": "Zdrowie", "id": "Kesehatan"}),
    ("sport", {"en": "Sport & leisure", "ru": "Спорт и отдых", "de": "Sport & Freizeit",
               "es": "Deporte y ocio", "fr": "Sport et loisirs", "pt": "Esporte e lazer",
               "pl": "Sport i rekreacja", "id": "Olahraga & rekreasi"}),
    ("shopping", {"en": "Shopping & money", "ru": "Покупки и деньги", "de": "Einkaufen & Geld",
                  "es": "Compras y dinero", "fr": "Achats et argent", "pt": "Compras e dinheiro",
                  "pl": "Zakupy i pieniądze", "id": "Belanja & uang"}),
    ("objects", {"en": "Objects", "ru": "Предметы", "de": "Objekte", "es": "Objetos", "fr": "Objets",
                 "pt": "Objetos", "pl": "Przedmioty", "id": "Benda"}),
    ("shapes", {"en": "Shapes & markers", "ru": "Фигуры и метки", "de": "Formen & Marker",
                "es": "Formas y marcadores", "fr": "Formes et repères", "pt": "Formas e marcadores",
                "pl": "Kształty i znaczniki", "id": "Bentuk & penanda"}),
    ("other", {"en": "Other", "ru": "Прочее", "de": "Sonstiges", "es": "Otros", "fr": "Autres",
               "pt": "Outros", "pl": "Inne", "id": "Lainnya"}),
]
CATEGORY_IDS = [c[0] for c in CATEGORIES]

# Font Awesome's ~70 web-UI categories folded onto product themes. An FA icon may sit in
# several FA categories and therefore in several product ones. Categories absent here
# (interfaces, spinners, toggle, code, …) contribute nothing, and an icon that ends up
# with no theme lands in `other`.
FA_CATEGORY_MAP = {
    "automotive": ["transport"], "vehicles": ["transport"], "maritime": ["transport"],
    "travel": ["transport"], "logistics": ["transport"], "moving": ["transport"],
    "animals": ["nature"], "autumn": ["nature"], "spring": ["nature"], "summer": ["nature"],
    "winter": ["nature"], "weather": ["nature"], "camping": ["nature", "sport"],
    "energy": ["objects"], "science": ["objects"],
    "buildings": ["buildings"], "hotel": ["buildings", "amenities"], "religion": ["buildings"],
    "education": ["buildings", "people"], "political": ["people"],
    "users-people": ["people"], "hands": ["people"], "gender": ["people"], "charity": ["people"],
    "social": ["people"], "childhood": ["people"], "emoji": ["people"], "accessibility": ["people"],
    "alert": ["safety"], "security": ["safety"], "status": ["safety"],
    "construction": ["safety", "objects"],
    "food": ["amenities"], "beverage": ["amenities"], "fruit-vegetable": ["amenities"],
    "games": ["sport"], "gaming-tabletop": ["sport"], "audio-video": ["amenities"],
    "music": ["amenities"], "chess": ["sport"],
    "health": ["health"], "medical": ["health"], "pharmacy": ["health"], "fitness": ["sport", "health"],
    "sports": ["sport"],
    "shopping": ["shopping"], "payments-shopping": ["shopping"], "currency": ["shopping"],
    "finance": ["shopping"], "business": ["objects"], "marketing": ["objects"],
    "objects": ["objects"], "household": ["objects"], "computers": ["objects"],
    "communication": ["objects"], "clothing": ["objects"], "holiday": ["objects"],
    "halloween": ["objects"], "science-fiction": ["objects"], "images": ["objects"],
    "writing": ["objects"], "design": ["objects"], "date-time": ["objects"], "files": ["objects"],
    "maps": ["shapes"], "shapes": ["shapes"], "arrows": ["shapes"], "mathematics": ["shapes"],
}

# Temaki ships a group per icon; Maki ships names only. Both map onto product themes here.
TEMAKI_GROUP_MAP = {
    "vehicles": ["transport"], "highways": ["transport"], "railways": ["transport"],
    "aerialways": ["transport"], "aeroways": ["transport"], "crossings": ["transport", "safety"],
    "cycling": ["transport", "sport"],
    "people": ["people"], "accessibility": ["people"],
    "utilities": ["objects"], "power": ["objects"], "telecom": ["objects"], "tools": ["objects"],
    "vending": ["amenities"], "mail": ["amenities"], "infrastructure": ["buildings", "objects"],
    "sports": ["sport"], "playground": ["sport", "amenities"],
    "water": ["nature"], "landforms": ["nature"], "plants": ["nature"], "animals": ["nature"],
    "snow": ["nature"], "camping": ["nature", "sport"],
    "buildings": ["buildings"], "home": ["buildings"], "religion": ["buildings"],
    "military": ["buildings", "safety"],
    "barriers": ["safety"], "security": ["safety"],
    "food": ["amenities"], "seating": ["amenities"], "information": ["amenities"], "arts": ["amenities"],
    "healthcare": ["health"],
    "shapes": ["shapes"],
    "clothes": ["shopping"], "bags": ["shopping"],
}

# Keyword → themes for Maki names (and a second opinion for Temaki names).
NAME_KEYWORD_MAP = {
    "transport": ["aerialway", "airfield", "airport", "bicycle", "bus", "car", "ferry", "fuel",
                  "harbor", "heliport", "highway", "parking", "rail", "road", "scooter", "taxi",
                  "terminal", "toll", "tunnel", "bridge", "charging", "entrance", "elevator", "gate",
                  "lift", "slipway", "snowmobile", "rocket", "roadblock", "barrier", "fence",
                  "traffic", "crossing", "station", "stop", "tram", "metro", "subway", "train",
                  "truck", "van", "boat", "ship", "plane", "helicopter", "bike", "moped", "motorcycle"],
    "nature": ["beach", "farm", "garden", "hot-spring", "landuse", "mountain", "natural", "park",
               "tree", "volcano", "water", "waterfall", "wetland", "zoo", "dog-park", "logging",
               "horse", "dam", "windmill", "watermill", "animal", "flower", "forest", "river",
               "lake", "snow", "cave", "rock", "sand", "grass", "bush", "plant"],
    "buildings": ["bank", "building", "castle", "church", "city", "college", "commercial",
                  "embassy", "fire-station", "historic", "home", "hospital", "industry",
                  "landmark", "library", "lighthouse", "lodging", "marae", "monument", "museum",
                  "observation", "place-of-worship", "police", "post", "prison", "ranger",
                  "religious", "residential", "school", "shelter", "stadium", "town", "village",
                  "warehouse", "cemetery", "communications-tower", "theatre", "cinema", "tower",
                  "hall", "house", "office", "factory", "temple", "mosque", "chapel"],
    "amenities": ["alcohol", "bakery", "bar", "bbq", "beer", "cafe", "confectionery",
                  "convenience", "drinking-water", "fast-food", "grocery", "ice-cream",
                  "information", "karaoke", "laundry", "nightclub", "picnic", "restaurant",
                  "teahouse", "telephone", "toilet", "waste-basket", "recycling", "bench",
                  "playground", "shelter", "fountain", "vending", "atm", "post", "mail", "wifi",
                  "charging", "shower", "lamp", "light", "bin", "trash", "litter"],
    "people": ["wheelchair", "person", "people", "child", "baby", "man", "woman", "worker",
               "pedestrian", "walk", "family", "senior", "student", "crowd"],
    "safety": ["caution", "danger", "defibrillator", "emergency", "fire", "police", "road-accident",
               "roadblock", "barrier", "warning", "hazard", "alarm", "lock", "camera", "fence"],
    "health": ["blood-bank", "dentist", "doctor", "hospital", "optician", "pharmacy", "veterinary",
               "defibrillator", "clinic", "medical", "health"],
    "sport": ["american-football", "amusement", "aquarium", "baseball", "basketball", "bowling",
              "campsite", "casino", "cricket", "fitness", "gaming", "golf", "pitch", "racetrack",
              "skateboard", "skiing", "soccer", "swimming", "table-tennis", "tennis", "volleyball",
              "playground", "sport", "climbing", "surf", "yoga", "gym", "bike", "boat", "ski"],
    "shopping": ["clothing", "furniture", "gift", "hairdresser", "hardware", "jewelry",
                 "shoe", "shop", "store", "suitcase", "watch", "market", "mall", "money", "bank"],
    "objects": ["art", "arrow", "globe", "heart", "mobile", "music", "paint", "star", "cross",
                "diamond", "phone", "tool", "box", "sign", "pole", "pipe", "cable", "antenna",
                "meter", "tank", "generator", "battery", "solar", "wind"],
    "shapes": ["circle", "marker", "square", "triangle", "star", "cross", "diamond", "arrow",
               "heart", "pin", "dot", "flag"],
}


def _words(name: str) -> list[str]:
    return [w for w in re.split(r"[-_]+", name.lower()) if w and w != "jp"]


def _label(name: str) -> str:
    words = _words(name)
    label = " ".join(words).capitalize()
    if name.lower().endswith("-jp"):
        label += " (JP)"
    return label


def _themes_from_name(name: str) -> list[str]:
    words = set(_words(name))
    found = []
    for cat, keys in NAME_KEYWORD_MAP.items():
        for key in keys:
            key_words = set(_words(key))
            if key_words <= words or key in name.lower():
                found.append(cat)
                break
    return found


def _ordered_unique(items):
    seen, out = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ── Font Awesome ────────────────────────────────────────────────────────────────

def _read_fa_categories(path: str) -> dict[str, list[str]]:
    """categories.yml is flat enough to read without PyYAML: `name:` / `  icons:` / `    - x`."""
    cats: dict[str, list[str]] = {}
    current = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^([a-z0-9-]+):\s*$", line)
            if m:
                current = m.group(1)
                cats[current] = []
                continue
            m = re.match(r"^\s+-\s+(\S+)\s*$", line)
            if m and current:
                cats[current].append(m.group(1))
    return cats


def load_font_awesome(root: str):
    meta = root if os.path.isfile(os.path.join(root, "icons.json")) else os.path.join(root, "metadata")
    with open(os.path.join(meta, "icons.json"), encoding="utf-8") as fh:
        icons = json.load(fh)
    fa_cats = _read_fa_categories(os.path.join(meta, "categories.yml"))
    by_icon: dict[str, list[str]] = {}
    for cat, names in fa_cats.items():
        for name in names:
            by_icon.setdefault(name, []).append(cat)

    out = []
    for name, entry in sorted(icons.items()):
        free_styles = [s for s in entry.get("free", []) if s in ("solid", "regular")]
        if not free_styles:
            continue  # brands, or Pro-only
        themes = _ordered_unique(
            t for cat in by_icon.get(name, []) for t in FA_CATEGORY_MAP.get(cat, [])
        ) or ["other"]
        terms = _ordered_unique([entry["label"].lower(), *_words(name), *(t.lower() for t in entry["search"]["terms"])])
        for style in free_styles:
            prefix = "fas" if style == "solid" else "far"
            out.append({
                "v": "%s fa-%s" % (prefix, name),
                "l": entry["label"] + (" (outline)" if style == "regular" else ""),
                "c": themes,
                "terms": terms,
            })
    return out


# ── SVG sets ─────────────────────────────────────────────────────────────────────

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def _svg_symbol(path: str, symbol_id: str) -> str:
    """One <symbol> from an upstream icon file: keep the drawing, drop fills, halos and metadata."""
    tree = ET.parse(path)
    root = tree.getroot()
    view_box = root.get("viewBox") or "0 0 %s %s" % (root.get("width", "15"), root.get("height", "15"))
    parts = []
    for child in list(root):
        tag = child.tag.split("}")[-1]
        if tag in ("metadata", "title", "desc", "defs", "style"):
            continue
        if child.get("stroke") and child.get("stroke-width"):
            continue  # Maki's white halo path — the pin provides the contrast
        for el in child.iter():
            for attr in ("fill", "stroke", "stroke-width", "style", "id", "class"):
                if attr in el.attrib:
                    del el.attrib[attr]
        parts.append(ET.tostring(child, encoding="unicode"))
    if not parts:
        raise ValueError("no drawable content in %s" % path)
    body = "".join(parts).replace(' xmlns="%s"' % SVG_NS, "")
    return '<symbol id="%s" viewBox="%s">%s</symbol>' % (symbol_id, view_box, body)


def load_svg_set(root: str, set_id: str, group_lookup):
    icons_dir = os.path.join(root, "icons")
    out, symbols = [], []
    for path in sorted(glob.glob(os.path.join(icons_dir, "*.svg"))):
        name = os.path.splitext(os.path.basename(path))[0]
        groups = group_lookup(name)
        themes = _ordered_unique([
            *(t for g in groups for t in TEMAKI_GROUP_MAP.get(g, [])),
            *_themes_from_name(name),
        ]) or ["other"]
        terms = _ordered_unique([*_words(name), *(g.lower() for g in groups)])
        out.append({
            "v": "%s:%s" % (set_id, name),
            "l": _label(name),
            "c": ["map", *themes],
            "terms": terms,
        })
        symbols.append(_svg_symbol(path, "%s-%s" % (set_id, name)))
    sprite = ('<svg xmlns="%s" style="display:none">%s</svg>\n' % (SVG_NS, "".join(symbols)))
    return out, sprite


def temaki_groups(root: str):
    with open(os.path.join(root, "data", "icons.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    return lambda name: data.get(name, {}).get("groups", [])


# ── Translations ────────────────────────────────────────────────────────────────

def load_term_tables() -> dict[str, dict[str, str]]:
    tables: dict[str, dict[str, str]] = {}
    for lang in LANGS[1:]:
        merged: dict[str, str] = {}
        for path in sorted(glob.glob(os.path.join(TERMS_DIR, lang, "*.json"))):
            with open(path, encoding="utf-8") as fh:
                for k, v in json.load(fh).items():
                    if isinstance(v, list):
                        v = " ".join(v)
                    merged[k.lower().strip()] = " ".join(v.lower().split())
        tables[lang] = merged
    return tables


def _terms_for(icon_terms: list[str], table: dict[str, str]) -> str:
    out = []
    for term in icon_terms:
        translated = table.get(term)
        if translated:
            out.extend(translated.split())
    return " ".join(_ordered_unique(out))


# ── Main ─────────────────────────────────────────────────────────────────────────

def build(args):
    fa = load_font_awesome(args.fa)
    maki, maki_sprite = load_svg_set(args.maki, "maki", lambda name: [])
    temaki, temaki_sprite = load_svg_set(args.temaki, "temaki", temaki_groups(args.temaki))
    counts = {"fa": len(fa), "maki": len(maki), "temaki": len(temaki)}
    for set_id, n in counts.items():
        if n == 0:
            sys.exit("icon set %s is empty — wrong path?" % set_id)

    all_icons = maki + temaki + fa  # map sets first: that is the picker's default order
    # Hand-authored civic vocabulary per icon ("bus stop" on the bus, "pothole" on the
    # road-damage glyph) — upstream terms describe the drawing, creators describe the
    # problem. Keys are icon values; values are comma-separated English phrases.
    extra_path = os.path.join(TERMS_DIR, "extra_en.json")
    if os.path.exists(extra_path):
        with open(extra_path, encoding="utf-8") as fh:
            extras = json.load(fh)
        by_value = {icon["v"]: icon for icon in all_icons}
        for value, phrases in extras.items():
            if value not in by_value:
                print("extra_en.json: unknown icon %s (skipped)" % value)
                continue
            by_value[value]["terms"] = _ordered_unique(
                by_value[value]["terms"] + [p.strip().lower() for p in phrases.split(",") if p.strip()]
            )
    for icon in all_icons:
        for theme in icon["c"]:
            assert theme in CATEGORY_IDS, (icon["v"], theme)

    unique_terms = sorted({t for icon in all_icons for t in icon["terms"]})
    if args.dump_terms:
        with open(args.dump_terms, "w", encoding="utf-8") as fh:
            fh.write("\n".join(unique_terms) + "\n")
        print("wrote %d unique English terms to %s" % (len(unique_terms), args.dump_terms))

    tables = load_term_tables()
    translated_counts = {}
    for lang, table in tables.items():
        translated_counts[lang] = sum(1 for t in unique_terms if t in table)

    catalog_icons = []
    for icon in all_icons:
        t = {"en": " ".join(_ordered_unique(w for term in icon["terms"] for w in term.split()))}
        for lang, table in tables.items():
            s = _terms_for(icon["terms"], table)
            if s:
                t[lang] = s
        catalog_icons.append({"v": icon["v"], "l": icon["l"], "c": icon["c"], "t": t})

    catalog = {
        "version": "fa-%s maki-%s temaki-%s" % (args.fa_version, args.maki_version, args.temaki_version),
        "languages": LANGS,
        "categories": [{"id": cid, "label": labels} for cid, labels in CATEGORIES],
        "icons": catalog_icons,
    }
    os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
    with open(CATALOG_PATH, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    with open(os.path.join(SPRITE_DIR, "maki.svg"), "w", encoding="utf-8") as fh:
        fh.write(maki_sprite)
    with open(os.path.join(SPRITE_DIR, "temaki.svg"), "w", encoding="utf-8") as fh:
        fh.write(temaki_sprite)

    print("icons: fa=%(fa)d maki=%(maki)d temaki=%(temaki)d" % counts)
    print("unique English terms: %d" % len(unique_terms))
    for lang in LANGS[1:]:
        print("  %s: %d/%d terms translated" % (lang, translated_counts.get(lang, 0), len(unique_terms)))
    print("wrote %s (%d bytes)" % (CATALOG_PATH, os.path.getsize(CATALOG_PATH)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fa", required=True, help="Font Awesome repo, or its metadata/ dir")
    p.add_argument("--maki", required=True, help="mapbox/maki checkout")
    p.add_argument("--temaki", required=True, help="rapideditor/temaki checkout")
    p.add_argument("--fa-version", default="5.15.4")
    p.add_argument("--maki-version", default=None)
    p.add_argument("--temaki-version", default=None)
    p.add_argument("--dump-terms", default=None, help="write the unique English term list here")
    args = p.parse_args()
    for attr, root in (("maki_version", args.maki), ("temaki_version", args.temaki)):
        if getattr(args, attr) is None:
            try:
                with open(os.path.join(root, "package.json"), encoding="utf-8") as fh:
                    setattr(args, attr, json.load(fh).get("version", "?"))
            except OSError:
                setattr(args, attr, "?")
    build(args)


if __name__ == "__main__":
    main()

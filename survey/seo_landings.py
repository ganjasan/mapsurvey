"""Single source of truth for the SEO landing pages.

Each :class:`SeoLanding` entry owns everything a marketing landing needs beyond
its template body: the public path, its sitemap crawl hints, its breadcrumb
trail, and its FAQ. The FAQ drives *both* the visible FAQ section and the
``FAQPage`` JSON-LD, so the two can't drift.

``robots.txt`` and ``sitemap.xml`` derive their landing entries from
``SEO_LANDINGS``, so a page can't have a route yet silently miss the sitemap,
the robots allow-list, or its structured data.

Landings are English-only today (the RU switcher is disabled until translations
land — see ``base_landing.html``), so copy here is plain English rather than
``gettext``-wrapped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from django.shortcuts import render

# Canonical production origin — matches the hardcoded canonical/og URLs in
# base_landing.html so breadcrumb `item` URLs are the indexable absolute URLs
# (and deterministic in tests, independent of the request host).
SITE_ORIGIN = "https://mapsurvey.org"

# Ship date of the current content wave. Bump an entry's ``lastmod`` when its
# content materially changes. Do NOT use "now": an always-fresh lastmod trains
# crawlers to distrust it.
LASTMOD_DEFAULT = "2026-07-21"


@dataclass(frozen=True)
class Crumb:
    name: str
    path: str  # absolute path, e.g. "/" or "/alternatives/"


@dataclass(frozen=True)
class QA:
    q: str
    a: str


@dataclass(frozen=True)
class SeoLanding:
    key: str
    path: str
    url_name: str
    template: str
    breadcrumbs: tuple  # tuple[Crumb, ...]
    faq: tuple          # tuple[QA, ...]
    changefreq: str = "monthly"
    priority: str = "0.8"
    lastmod: str = LASTMOD_DEFAULT


HOME = Crumb("Home", "/")
ALTERNATIVES = Crumb("Alternatives", "/alternatives/")

# ---------------------------------------------------------------------------
# Reusable answers (universal product facts shared across several pages). Keep
# each page's *set* of questions distinct, but factual answers can be shared.
# ---------------------------------------------------------------------------
_A_FREE = (
    "Yes. Mapsurvey is open source (AGPLv3) and free to start — you can create "
    "and publish a map-based survey without paying, and self-host the whole "
    "platform at no licence cost."
)
_A_SELFHOST = (
    "Yes. Mapsurvey ships as a Docker stack you can run on your own "
    "infrastructure, so response data stays on servers you control — useful for "
    "GDPR and data-residency requirements."
)
_A_ACCOUNT = (
    "No. Respondents open a public link and answer on the map — no sign-up or "
    "login required. Only survey creators need an account."
)
_A_EXPORT = (
    "Every response — including map geometry — exports as GeoJSON plus a CSV for "
    "non-spatial answers, so results drop straight into QGIS, ArcGIS, or a "
    "spreadsheet. You own the data."
)
_A_GEO = (
    "Respondents can drop points, draw lines (routes), and outline polygons "
    "(areas) directly on the map, alongside ordinary survey questions."
)


SEO_LANDINGS = (
    SeoLanding(
        key="for_planners",
        path="/for-planners/",
        url_name="for_planners",
        template="for_planners.html",
        breadcrumbs=(HOME, Crumb("For Urban Planners", "/for-planners/")),
        faq=(
            QA("Is Mapsurvey free for urban-planning teams?", _A_FREE),
            QA("What can residents mark on the map?", _A_GEO),
            QA("Can I export results into QGIS or ArcGIS?", _A_EXPORT),
            QA("Do residents need to create an account to take part?", _A_ACCOUNT),
            QA("Can we self-host it for data control?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="for_researchers",
        path="/for-researchers/",
        url_name="for_researchers",
        template="for_researchers.html",
        breadcrumbs=(HOME, Crumb("For Researchers", "/for-researchers/")),
        faq=(
            QA("Is Mapsurvey suitable for PPGIS and participatory research?",
               "Yes — it is built for public-participation GIS: point, line, and "
               "polygon input captured against your own questions, exported as "
               "analysis-ready GeoJSON/CSV."),
            QA("How do I get the raw spatial data for analysis?", _A_EXPORT),
            QA("Do participants need an account?", _A_ACCOUNT),
            QA("Can I self-host for ethics/data-governance requirements?", _A_SELFHOST),
            QA("Is it really free to start?", _A_FREE),
        ),
    ),
    SeoLanding(
        key="for_government",
        path="/for-government/",
        url_name="for_government",
        template="for_government.html",
        breadcrumbs=(HOME, Crumb("For Local Government", "/for-government/")),
        faq=(
            QA("Is this a free community-engagement platform for local government?", _A_FREE),
            QA("Can we host it on our own infrastructure?", _A_SELFHOST),
            QA("Do residents need to register to respond?", _A_ACCOUNT),
            QA("What map input can residents give?", _A_GEO),
            QA("Can we export results for our GIS team?", _A_EXPORT),
        ),
    ),
    SeoLanding(
        key="for_educators",
        path="/for-educators/",
        url_name="for_educators",
        template="for_educators.html",
        breadcrumbs=(HOME, Crumb("For Educators", "/for-educators/")),
        faq=(
            QA("Is Mapsurvey free to use in the classroom?", _A_FREE),
            QA("Do students need to install anything?",
               "No. Students open a link in the browser and mark the map — no "
               "install, and no account needed to respond."),
            QA("Can students export the data for coursework?", _A_EXPORT),
            QA("What kinds of map questions can students build?", _A_GEO),
            QA("Can the university self-host it?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="for_consultants",
        path="/for-consultants/",
        url_name="for_consultants",
        template="for_consultants.html",
        breadcrumbs=(HOME, Crumb("For Consultants", "/for-consultants/")),
        faq=(
            QA("Are there per-project or per-survey fees?",
               "No. The open-source path has no per-project or per-survey "
               "licence fees — run as many engagements as you like and self-host "
               "if you want full control."),
            QA("Can I hand clients GIS-ready deliverables?", _A_EXPORT),
            QA("Do respondents need accounts?", _A_ACCOUNT),
            QA("Can I self-host for client data separation?", _A_SELFHOST),
            QA("Is it free to start?", _A_FREE),
        ),
    ),
    SeoLanding(
        key="community_engagement_platform",
        path="/community-engagement-platform/",
        url_name="community_engagement_platform",
        template="community_engagement_platform.html",
        breadcrumbs=(HOME, Crumb("Community Engagement Platform", "/community-engagement-platform/")),
        faq=(
            QA("Is Mapsurvey a free, open-source community-engagement platform?", _A_FREE),
            QA("Can we self-host it?", _A_SELFHOST),
            QA("What map input can the community give?", _A_GEO),
            QA("Do community members need an account to take part?", _A_ACCOUNT),
            QA("Do we own the data we collect?", _A_EXPORT),
        ),
    ),
    SeoLanding(
        key="public_consultation_software",
        path="/public-consultation-software/",
        url_name="public_consultation_software",
        template="public_consultation_software.html",
        breadcrumbs=(HOME, Crumb("Public Consultation Software", "/public-consultation-software/")),
        faq=(
            QA("Is this free public-consultation software?", _A_FREE),
            QA("Can residents comment on specific locations?", _A_GEO),
            QA("Do respondents need to sign up to give feedback?", _A_ACCOUNT),
            QA("Can we export consultation responses for the record?", _A_EXPORT),
            QA("Can it be self-hosted for public-sector data rules?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="civic_engagement",
        path="/civic-engagement/",
        url_name="civic_engagement",
        template="civic_engagement.html",
        breadcrumbs=(HOME, Crumb("Civic Engagement", "/civic-engagement/")),
        faq=(
            QA("What is map-based civic engagement?",
               "It lets residents show exactly where something matters — pinning "
               "places, drawing routes, outlining areas — instead of leaving vague "
               "free-text comments, giving officials location-specific evidence."),
            QA("Is Mapsurvey free for civic-engagement projects?", _A_FREE),
            QA("Do participants need an account?", _A_ACCOUNT),
            QA("Can we export the results?", _A_EXPORT),
            QA("Can we self-host it?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="participatory_budgeting",
        path="/participatory-budgeting/",
        url_name="participatory_budgeting",
        template="participatory_budgeting.html",
        breadcrumbs=(HOME, Crumb("Participatory Budgeting", "/participatory-budgeting/")),
        faq=(
            QA("Can Mapsurvey run the spatial side of participatory budgeting?",
               "Yes — residents pin exactly where investment is needed "
               "(playgrounds, crossings, lighting, greening). It captures the "
               "location input for a PB programme; it is not a budget-allocation "
               "or voting-ledger module."),
            QA("Is it free to start?", _A_FREE),
            QA("Do residents need an account to submit a location?", _A_ACCOUNT),
            QA("Can we export the pinned proposals for scoring?", _A_EXPORT),
            QA("Can we self-host it?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="maptionnaire_alternative",
        path="/alternatives/maptionnaire/",
        url_name="maptionnaire_alternative",
        template="maptionnaire_alternative.html",
        breadcrumbs=(HOME, ALTERNATIVES, Crumb("Maptionnaire Alternative", "/alternatives/maptionnaire/")),
        faq=(
            QA("Is Mapsurvey a free alternative to Maptionnaire?",
               "Yes — Mapsurvey is a free, open-source alternative for map-based "
               "surveys, with no per-survey fee and no free-tier gate on the "
               "open-source path."),
            QA("Does it support the same point, line, and polygon input?", _A_GEO),
            QA("Can I export to GeoJSON like a GIS-first tool?", _A_EXPORT),
            QA("Can I self-host or keep data in the EU?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="social_pinpoint_alternative",
        path="/alternatives/social-pinpoint/",
        url_name="social_pinpoint_alternative",
        template="social_pinpoint_alternative.html",
        breadcrumbs=(HOME, ALTERNATIVES, Crumb("Social Pinpoint Alternative", "/alternatives/social-pinpoint/")),
        faq=(
            QA("Is Mapsurvey an open-source alternative to Social Pinpoint?",
               "Yes — it is an open-source, self-hostable alternative for "
               "map-based engagement, with no per-project licence on the "
               "open-source path."),
            QA("Can respondents draw, not just drop markers?",
               "Yes — respondents can drop points and also draw lines (routes) "
               "and polygons (areas), then you export the geometry."),
            QA("Can I export the raw spatial data?", _A_EXPORT),
            QA("Can I self-host it?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="metroquest_alternative",
        path="/alternatives/metroquest/",
        url_name="metroquest_alternative",
        template="metroquest_alternative.html",
        breadcrumbs=(HOME, ALTERNATIVES, Crumb("MetroQuest Alternative", "/alternatives/metroquest/")),
        faq=(
            QA("Why look for a MetroQuest alternative?",
               "MetroQuest has been folded into the Open Point suite. Mapsurvey "
               "is a free, open-source option for map-based public input you can "
               "self-host and fully export."),
            QA("Does Mapsurvey support drawing on the map, not just markers?",
               "Yes — points, lines, and polygons, alongside standard survey "
               "questions."),
            QA("Can I export the results?", _A_EXPORT),
            QA("Is it free and self-hostable?", _A_SELFHOST),
        ),
    ),
)

_BY_KEY = {landing.key: landing for landing in SEO_LANDINGS}


def get_landing(key: str) -> SeoLanding:
    return _BY_KEY[key]


def _abs(path: str) -> str:
    return f"{SITE_ORIGIN}{path}"


def build_faqpage_jsonld(faq) -> str:
    """Return a valid ``FAQPage`` JSON-LD string built from a QA list.

    Uses ``json.dumps`` so quotes/apostrophes in answers are always escaped.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item.q,
                "acceptedAnswer": {"@type": "Answer", "text": item.a},
            }
            for item in faq
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def build_breadcrumb_jsonld(crumbs) -> str:
    """Return a valid ``BreadcrumbList`` JSON-LD string with absolute item URLs."""
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": crumb.name,
                "item": _abs(crumb.path),
            }
            for i, crumb in enumerate(crumbs)
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def build_story_collection_jsonld(request, stories) -> str:
    """Return a ``CollectionPage`` JSON-LD for the stories index.

    ``stories`` is an iterable of Story instances; each becomes an ``ItemList``
    entry with an absolute detail URL. Built with ``json.dumps`` for safe escaping.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Mapsurvey Stories",
        "url": _abs("/stories/"),
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": _abs(f"/stories/{story.slug}/"),
                    "name": story.title,
                }
                for i, story in enumerate(stories)
            ],
        },
    }
    return json.dumps(data, ensure_ascii=False)


def render_seo_landing(request, key: str):
    """Render an SEO landing, injecting its FAQ + structured data from the registry."""
    from .events import capture_signup_source  # local import: events is import-light

    landing = _BY_KEY[key]
    capture_signup_source(request)
    context = {
        "faq_items": landing.faq,
        "faqpage_jsonld": build_faqpage_jsonld(landing.faq) if landing.faq else "",
        "breadcrumb_jsonld": build_breadcrumb_jsonld(landing.breadcrumbs) if landing.breadcrumbs else "",
    }
    return render(request, landing.template, context)

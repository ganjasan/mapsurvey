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
        lastmod="2026-10-06",
        faq=(
            QA("What is a community engagement platform?",
               "Software a council, agency or consultancy uses to collect public input "
               "online: surveys, comments and, in a map-based platform like Mapsurvey, "
               "places. Residents open a link, mark the locations their answer is about "
               "and answer the questions attached to each one; the team gets a map and a "
               "table of every response instead of a mailbox of free text."),
            QA("How much does a community engagement platform cost?",
               "Mapsurvey is free for a real project: unlimited surveys, respondents and "
               "team members at $0, hosted or self-hosted. Pro is $49 a month or $490 a "
               "year per workspace, with any number of users. The established vendors "
               "sell by quote only: none publishes a current price list, and a council "
               "learns the figure from sales, usually per instance and per year."),
            QA("Is there a free community engagement platform for local government?",
               "Yes. Mapsurvey's Free plan is the full product, not a trial: every "
               "question type including point, line and polygon input, follow-up "
               "questions on each place, 75 languages and every export format. It is "
               "open source (AGPLv3), so a council IT team can also run it on its own "
               "servers at no licence cost."),
            QA("What can residents mark on the map?", _A_GEO),
            QA("Do community members need an account to take part?", _A_ACCOUNT),
            QA("Where is the data hosted, and can we self-host?",
               "The hosted service runs in the United States today (Render, Oregon). "
               "Teams that need EU data residency self-host the Docker stack on their "
               "own infrastructure; a choice of hosting region is on the Pro roadmap. "
               "Either way the data is yours to export and delete."),
            QA("Do we own the data we collect?", _A_EXPORT),
        ),
    ),
    SeoLanding(
        key="citizen_engagement_platform",
        path="/citizen-engagement-platform/",
        url_name="citizen_engagement_platform",
        template="citizen_engagement_platform.html",
        breadcrumbs=(HOME, Crumb("Citizen Engagement Platform", "/citizen-engagement-platform/")),
        lastmod="2026-10-06",
        # Change citizen-engagement-landing (#252): the questions are the ones Search Console
        # shows for this cluster, in the buyer's words.
        faq=(
            QA("What is a citizen engagement platform?",
               "Software a local government uses to involve residents in its decisions "
               "online: consultations, surveys, idea collection and, in a map-based "
               "platform like Mapsurvey, places. Vendors also call it a citizen "
               "participation platform or citizen engagement software for local "
               "government. Residents open a link, mark the locations their answer is "
               "about and answer the questions attached to each one; the council gets a "
               "map and a table of every response, exportable to its GIS."),
            QA("Which citizen engagement platforms offer a free trial or a free plan for governments?",
               "Mapsurvey offers a free plan rather than a trial: unlimited surveys, "
               "respondents and team members at $0, hosted or self-hosted, with every "
               "question type and every export format. Most established vendors offer a "
               "demo or a scoped trial through their sales team; Go Vocal also publishes a "
               "free self-hosted edition of its software."),
            QA("What does a citizen engagement platform cost for a small jurisdiction?",
               "On Mapsurvey the price is the same for a parish council and a county: "
               "free, or Pro at $49 a month or $490 a year per workspace with any number "
               "of users, surveys and responses. There is no per-resident, per-seat or "
               "per-project metering. The established platforms license per instance "
               "and per year, by quote; a small jurisdiction pays for the same instance "
               "as a large one."),
            QA("Who owns the data we collect, and can we export it?",
               "You do. Every response, including the map geometry, exports at any time "
               "as GeoJSON, CSV, Excel, GeoPackage, Shapefile or KML, so it goes straight "
               "into QGIS, ArcGIS or a spreadsheet. A survey and its responses can be "
               "deleted by its owner. Self-hosting the open-source code puts the database "
               "itself on your servers."),
            QA("What are the uptime and support arrangements?",
               "The hosted service has no contractual SLA today. Deploys are zero-downtime, "
               "the stack is monitored, and incidents are fixed by the developer who runs "
               "it. A council that needs an uptime guarantee can self-host the same Docker "
               "stack under its own IT policy. Pro includes direct support from the "
               "developer; Free is supported by email and the public issue tracker."),
            QA("Do residents need an account to take part?", _A_ACCOUNT),
            QA("Where is the data hosted, and does it meet our residency rules?",
               "The hosted service runs in the United States today (Render, Oregon). "
               "Councils that need the data to stay in their own jurisdiction self-host "
               "the Docker stack at no licence cost; a choice of hosting region is on the "
               "Pro roadmap. Either way the data is yours to export and delete."),
        ),
    ),
    SeoLanding(
        key="public_consultation_software",
        path="/public-consultation-software/",
        url_name="public_consultation_software",
        template="public_consultation_software.html",
        breadcrumbs=(HOME, Crumb("Public Consultation Software", "/public-consultation-software/")),
        lastmod="2026-10-06",
        faq=(
            QA("What is public consultation software?",
               "Software for running a consultation online: publishing a proposal, "
               "collecting responses from residents and stakeholders, and turning them "
               "into a report. Mapsurvey is the map-based kind: the scheme is shown on a "
               "map, people comment on the exact site, route or junction, and every "
               "response carries a location you can analyse in GIS."),
            QA("Is there free council consultation software?",
               "Yes. Mapsurvey's Free plan runs a complete consultation at $0, with no "
               "cap on responses, and the open-source code can be hosted by a council's "
               "own IT. Pro, at $49 a month or $490 a year per workspace, adds public "
               "results pages and direct support. UK statutory platforms are licensed "
               "per instance and per year, by quote; the rates sit on G-Cloud rather "
               "than on the vendors' own sites."),
            QA("Can residents comment on a specific location in the proposal?", _A_GEO),
            QA("How do we show consultees the plans?",
               "Upload the proposal as a reference layer (GeoJSON, from any GIS). "
               "Respondents see the scheme on the map and can answer questions about "
               "each feature in it, such as a proposed crossing or a new route, or mark "
               "their own places alongside it."),
            QA("How do responses get into the consultation report?",
               "Export every response, including the geometry, as GeoJSON, CSV, Excel, "
               "GeoPackage, Shapefile or KML, or publish an aggregated public results "
               "page for the record. Individual free-text answers are never published."),
            QA("Do respondents need to sign up to give feedback?", _A_ACCOUNT),
            QA("Can it be self-hosted for public-sector data rules?", _A_SELFHOST),
        ),
    ),
    SeoLanding(
        key="civic_engagement",
        path="/civic-engagement/",
        url_name="civic_engagement",
        template="civic_engagement.html",
        breadcrumbs=(HOME, Crumb("Civic Engagement", "/civic-engagement/")),
        lastmod="2026-10-06",
        faq=(
            QA("What is map-based civic engagement?",
               "It lets residents show exactly where something matters, by pinning "
               "places, drawing routes and outlining areas, instead of leaving vague "
               "free-text comments. Officials get location-specific evidence they can "
               "count, map and act on."),
            QA("How do you engage people on a map?",
               "Ask one concrete question per map (\"Where do you feel unsafe "
               "cycling?\"), let people answer by marking the place, attach one or two "
               "short follow-up questions to each mark, share a link that needs no "
               "account, and show the results back on a public map so participants see "
               "their input was used."),
            QA("What is the difference between civic engagement and community engagement?",
               "In practice the terms overlap. Civic engagement usually means residents "
               "taking part in public decisions, from consultations to participatory "
               "budgeting; community engagement is the organisation's side of the same "
               "relationship, and a community engagement platform is the software that "
               "runs it. Mapsurvey serves both with the same map."),
            QA("Is Mapsurvey free for civic engagement projects?",
               "Yes. The Free plan is $0 with unlimited surveys and respondents; Pro is "
               "$49 a month or $490 a year per workspace for teams that want public "
               "results pages and direct support. No per-project fees either way."),
            QA("Can one workspace run civic engagement for a whole city?",
               "Yes. A workspace holds any number of surveys, team members and "
               "respondents, each survey has its own public link and results page, and "
               "every answer exports to the city's GIS."),
            QA("Do participants need an account?", _A_ACCOUNT),
            QA("Can we export the results?", _A_EXPORT),
        ),
    ),
    SeoLanding(
        key="participatory_budgeting",
        path="/participatory-budgeting/",
        url_name="participatory_budgeting",
        template="participatory_budgeting.html",
        breadcrumbs=(HOME, Crumb("Participatory Budgeting", "/participatory-budgeting/")),
        lastmod="2026-10-06",
        faq=(
            QA("Can Mapsurvey run participatory budgeting?",
               "It runs the spatial side: residents pin exactly where investment is "
               "needed, propose and describe projects in place, and react to shortlisted "
               "locations on a shared map. It is not a budget-allocation or ballot "
               "module; for the final vote on a fixed budget, use a PB voting tool."),
            QA("What does participatory budgeting software cost?",
               "Mapsurvey is free at $0 for unlimited proposals and respondents, and "
               "$49 a month or $490 a year per workspace on Pro. Full PB suites are "
               "mostly quote-only; open-source suites such as Decidim are free to "
               "license but need hosting and setup."),
            QA("How do residents propose a project on the map?",
               "They open the link, drop a pin or outline an area, and answer the "
               "questions attached to it: what to build, why, a photo. No account is "
               "needed, and the map works on a phone."),
            QA("Can residents react to each other's proposals?",
               "Yes. Shortlisted proposals can be shown as a layer on the map, and an "
               "\"objects on the map\" question lets residents give each one a thumbs "
               "up or down and a comment. Reactions are one per session, without voter "
               "authentication, so use them to prioritise, not as a binding ballot."),
            QA("Can we export the pinned proposals for scoring?", _A_EXPORT),
            QA("Do residents need an account to submit a location?", _A_ACCOUNT),
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
        lastmod="2026-10-06",
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

    from .topics import for_landing, stories_for

    landing = _BY_KEY[key]
    capture_signup_source(request)
    # Change story-topics: the stories that prove this page, by the topic that owns it.
    # Alternatives pages own no topic and render no block.
    topic = for_landing(key)
    context = {
        "topic": topic,
        "topic_stories": list(stories_for(topic)) if topic else [],
        "faq_items": landing.faq,
        "faqpage_jsonld": build_faqpage_jsonld(landing.faq) if landing.faq else "",
        "breadcrumb_jsonld": build_breadcrumb_jsonld(landing.breadcrumbs) if landing.breadcrumbs else "",
    }
    return render(request, landing.template, context)

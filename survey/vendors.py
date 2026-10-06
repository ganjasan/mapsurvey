"""Vendor fact registry for the comparison pages (change market-guide-landscape-hub, #259).

ONE source of truth for every claim the marketing site makes about another vendor. The market
guide (`/participatory-mapping-tools/`) and the `/alternatives/` pages render their comparison
tables from these rows, so a correction here reaches every page at once and the pages can never
disagree with each other (#196 was two pages drifting apart).

Rules, enforced at import by `_validate()` and in `VendorRegistryTest`:

- Every fact is a `Fact(text, source, verified)`: the text the page renders, the PUBLIC `https://`
  page it was read from, and the ISO date it was read. A fact without a URL is not a fact.
- "Not published" is itself a fact: the page we read does not say. Its source is that page.
- No price figure for any vendor but Mapsurvey (owner rule 2026-10-06, issues #253/#259):
  pricing cells name the MODEL (per licence / per instance / per contributor / quote only / free
  software), whether a free tier or trial exists and its conditions, and whether a rate is listed
  (the vendor's site, UK G-Cloud) or available from sales only. `test_no_competitor_price_figure…`
  scans every fact text.
- Facts come from the vendor's own pages, documentation or a public procurement listing — never
  from a dossier, a review site or an AI answer. Dossiers in the ops repo are leads to a page,
  not sources.

To correct a cell: change the text, the source if it moved, and the date you re-read it.
"""
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Fact:
    text: str
    source: str
    verified: str  # ISO date the page was read

    @property
    def host(self) -> str:
        return urlsplit(self.source).netloc.replace("www.", "", 1)


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str        # column heading
    ask: str          # one line: what a buyer should ask about it


@dataclass(frozen=True)
class Category:
    key: str
    title: str
    purpose: str      # what the tools in it are for
    buyers: str       # who buys them


@dataclass(frozen=True)
class ExtraRow:
    """A row only one `/alternatives/` page needs (MetroQuest's post-launch edits, say)."""
    label: str
    ours: str
    theirs: Fact


@dataclass(frozen=True)
class Vendor:
    key: str
    name: str
    maker: str
    url: str
    category: str
    summary: str
    facts: dict               # Criterion.key -> Fact, every CRITERIA key present
    landing_key: str = ""     # seo_landings key of its /alternatives/ page, if one exists
    extras: tuple = ()        # ExtraRow, rendered after the criteria on the alternatives page
    gaps: tuple = ()          # only Mapsurvey states its own

    def fact(self, key: str) -> Fact:
        return self.facts[key]

    @property
    def ordered_facts(self):
        return [self.facts[c.key] for c in CRITERIA]

    @property
    def verified_on(self) -> str:
        """The EARLIEST date among the facts: the honest one to print for the row."""
        return min(f.verified for f in self.facts.values())

    @property
    def sources(self):
        """Distinct source URLs with the date each was read, in first-seen order."""
        seen = {}
        for f in list(self.facts.values()) + [e.theirs for e in self.extras]:
            seen.setdefault(f.source, f.verified)
        return [{"url": url, "verified": when, "host": urlsplit(url).netloc.replace("www.", "", 1)}
                for url, when in seen.items()]


CRITERIA = (
    Criterion("geometry", "What respondents can draw",
              "Can a resident draw a route or outline an area, or only drop a pin? Lines and "
              "polygons are what mobility, green-space and land-use questions need."),
    Criterion("export", "Export formats",
              "Does the geometry come back as GeoJSON or Shapefile for your GIS, or only as a "
              "spreadsheet of coordinates?"),
    Criterion("licence", "Open source / self-hosting",
              "Can you run it on your own servers, and under which licence? Self-hosting is the "
              "surest answer to a data-residency requirement."),
    Criterion("hosting", "Hosting region and GDPR posture",
              "Where does the hosted service keep the data, and what does the vendor state about "
              "GDPR, ISO 27001 and accessibility?"),
    Criterion("pricing", "Pricing model",
              "Per licence, per instance, per project, per contributor, or on request? Whether a "
              "rate is listed anywhere public is itself a useful fact."),
    Criterion("free", "Free tier or trial",
              "Is there a free plan you can run a real project on, a time-limited trial, or only a "
              "sandbox that cannot publish?"),
    Criterion("public_results", "Public results page",
              "Can residents see what others said, live, without an account?"),
    Criterion("onboarding", "How you start",
              "Self-serve sign-up the same day, or a demo request and a sales-led onboarding?"),
    Criterion("languages", "Languages",
              "How many languages can the respondent side run in, and is translation included?"),
)

CATEGORIES = (
    Category("ppgis", "Specialised map-based survey tools",
             "Public-participation GIS (PPGIS) tools: the survey is the product and the map is the "
             "main question. Respondents place points, draw routes and outline areas, answer "
             "follow-up questions about each, and the result is a spatial dataset.",
             "Planning departments, transport and mobility consultancies, universities running "
             "PPGIS research, and parish or town councils that need one map survey rather than a "
             "participation portal."),
    Category("engagement", "Engagement platforms with a map feature",
             "Participation suites that run a council's whole engagement programme — project pages, "
             "surveys, ideas, forums, participatory budgeting — with a map tool among many. The "
             "map is usually a pin-drop with a comment.",
             "Local and regional governments buying a standing portal, usually through procurement "
             "and with a named customer-success manager; consultancies that run engagement for them."),
    Category("field", "Field data collection apps",
             "Mobile apps for trained staff and volunteers collecting observations offline: GPS "
             "points, traces and shapes with attribute forms and photos, synced to a server. Built "
             "for enumerators, not for anonymous residents following a link.",
             "Ecology and archaeology teams, utilities, humanitarian organisations, and anyone "
             "already standing inside the Esri or QGIS ecosystem."),
    Category("open_source", "Open-source participation frameworks",
             "Free software a city installs and operates itself (or pays a partner to host): "
             "proposals, debates, voting and participatory budgeting, with an address geocoded to a "
             "point on a map. Drawing is not the point.",
             "Cities with an IT department or a civic-tech partner, and governments whose "
             "procurement rules favour open source."),
    Category("forms", "Generic form builders with a location question",
             "Everyday form tools where a location is one field among many: a pin or an address, "
             "no drawing, no spatial export. Enough for 'where do you live', not for 'where is the "
             "problem'.",
             "Teams that already pay for the form tool and need one address per response."),
)

_CATEGORY_KEYS = {c.key for c in CATEGORIES}
_CRITERION_KEYS = [c.key for c in CRITERIA]

D = "2026-10-06"  # the day every page below was read

# --- Mapsurvey -------------------------------------------------------------------------------
_MS_TRUST = "https://mapsurvey.org/trust/"
_MS_PRO = "https://mapsurvey.org/pro/"
_MS_HOME = "https://mapsurvey.org/"
_MS_GITHUB = "https://github.com/ganjasan/mapsurvey"

MAPSURVEY = Vendor(
    key="mapsurvey", name="Mapsurvey", maker="Mapsurvey", url=_MS_HOME, category="ppgis",
    summary="Map-based surveys where respondents place points, draw lines and outline polygons, "
            "each with follow-up questions; results come back as GIS files and a public results page.",
    facts={
        "geometry": Fact("Points, lines and polygons, each with follow-up questions", _MS_HOME, D),
        "export": Fact("GeoJSON, GeoPackage, Shapefile, KML, CSV and Excel", _MS_HOME, D),
        "licence": Fact("Yes, AGPLv3; Docker stack on your own servers", _MS_GITHUB, D),
        "hosting": Fact("Hosted in the United States (Render, Oregon); self-host anywhere for EU "
                        "residency; no formal accessibility audit yet", _MS_TRUST, D),
        "pricing": Fact("Published: free, or one flat workspace price", _MS_PRO, D),
        "free": Fact("Free plan, unlimited surveys and responses, no time limit", _MS_PRO, D),
        "public_results": Fact("Yes, a public results page per survey, no account needed", _MS_HOME, D),
        "onboarding": Fact("Self-serve sign-up; the developer answers questions directly", _MS_HOME, D),
        "languages": Fact("75, translation included", _MS_HOME, D),
    },
    gaps=(
        "No participatory budgeting, idea walls or voting on other people's entries.",
        "No discussion between respondents: a survey collects, it does not host a forum.",
        "No SSO or identity federation for respondents or editors.",
        "No formal WCAG conformance audit or ISO 27001 certificate to hand to procurement.",
        "The hosted service runs in the United States; EU residency means self-hosting.",
    ),
)

# --- Specialised map-based survey tools -------------------------------------------------------
_MT_SUB = "https://www.maptionnaire.com/subscription"
_MT_COMPL = "https://maptionnaire.com/compliance"
_PM_HOME = "https://www.partimap.eu/en"
_PM_TERMS = "https://www.partimap.eu/en/p/DEMO-in-English/5"
_PM_GITHUB = "https://github.com/k-monitor/partimap"

# --- Engagement platforms with a map feature --------------------------------------------------
_GV_MAP = "https://www.govocal.com/mapping"
_GV_OSS = "https://www.govocal.com/open-source"
_GV_FEAT = "https://govocal.com/platform-features"
_GV_GCLOUD = "https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/720131980361862"
_OP_TOOLS = "https://www.openpoint.com/products/community-engagement/community-engagement-tools/"
_OP_PRICING = "https://www.openpoint.com/plans/request-pricing"
_OP_REPORT = "https://learn.socialpinpoint.com/social-map/social-map-reporting"
_OP_FAQ = "https://learn.socialpinpoint.com/start-here/frequently-asked-questions"
_OP_A11Y = "https://learn.socialpinpoint.com/accessibility"
_OP_SMAP = "https://learn.socialpinpoint.com/social-map"
_OP_MQ_ACQ = "https://www.socialpinpoint.com/social-pinpoint-acquires-metroquest/"
_CS_GEO = "https://www.delib.net/citizen_space/geospatial"
_CS_GCLOUD = "https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/439053715790386"
_CP_GCLOUD = "https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/309165893513448"
_CP_HOME = "https://zencity.io/uk"
_EHQ_PLACES = "https://go.engagementhq.com/places-tool"
_EHQ_PROD = "https://granicus.com/product/engagementhq/"
_EHQ_GCLOUD = "https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/394920096965516"
_MQ_PROD = "https://metroquest.com/product/"
_MQ_PRICING = "https://metroquest.com/pricing/"
_MQ_TXDOT = "https://ftp.dot.state.tx.us/pub/txdot/get-involved/misc/Metroquest%20Factsheet%202022-0104.pdf"

# --- Field data collection --------------------------------------------------------------------
_S123_TYPES = "https://doc.arcgis.com/en/survey123/create/main/question-types-overview.htm"
_S123_EXPORT = "https://doc.arcgis.com/en/survey123/analyze/viewresults.htm"
_S123_OVERVIEW = "https://www.esri.com/en-us/arcgis/products/arcgis-survey123/overview"
_S123_REGIONS = "https://trust.arcgis.com/en/security/regional-hosting.htm"
_KOBO_GPS = "https://support.kobotoolbox.org/mapping_gps.html"
_KOBO_GDPR = "https://support.kobotoolbox.org/gdpr.html"
_KOBO_ACCOUNT = "https://support.kobotoolbox.org/creating_account.html"
_KOBO_PLANS = "https://community.kobotoolbox.org/t/update-about-limits-for-free-accounts/44198"
_KOBO_GITHUB = "https://github.com/kobotoolbox/kpi"
_MM_FEATURES = "https://merginmaps.com/product/survey-features"
_MM_PRICING = "https://merginmaps.com/pricing"
_MM_HOME = "https://merginmaps.com/"

# --- Open-source participation frameworks -----------------------------------------------------
_DC_HOME = "https://decidim.org/"
_DC_FEAT = "https://decidim.org/features/"
_DC_MAPS = "https://docs.decidim.org/en/develop/services/maps"
_DC_EXPORT = "https://meta.decidim.org/processes/roadmap/f/122/proposals/16871"
_DC_GITHUB = "https://github.com/decidim/decidim"
_CD_HOME = "https://consuldemocracy.org/"
_CD_ADMIN = "https://docs.consuldemocracy.org/docs_general/interfaces/administration"
_CD_GITHUB = "https://github.com/consuldemocracy/consuldemocracy"

# --- Generic form builders --------------------------------------------------------------------
_JF_GEO = "https://www.jotform.com/help/247-add-google-map-geolocation-marker-to-your-form"
_JF_EXPORT = "https://www.jotform.com/help/73-how-to-download-form-submissions-as-excel-csv-pdf/"
_JF_PRICING = "https://www.jotform.com/pricing/"
_GF_TYPES = "https://support.google.com/docs/answer/7322334"
_GF_RESP = "https://support.google.com/docs/answer/2917686"
_GF_PROD = "https://workspace.google.com/products/forms/"

NP = "Not published"

VENDORS = (
    MAPSURVEY,
    Vendor(
        key="maptionnaire", name="Maptionnaire", maker="Mapita Oy, Helsinki",
        url="https://www.maptionnaire.com/", category="ppgis", landing_key="maptionnaire_alternative",
        summary="The reference PPGIS product: points, lines and areas with follow-up questions, "
                "public project pages and reports on the higher tiers, sold by annual subscription.",
        facts={
            "geometry": Fact("Points, lines and areas (polygons)", _MT_SUB, D),
            "export": Fact("Shapefile, GeoJSON, Excel with coordinates, PNG map image", _MT_SUB, D),
            "licence": Fact("No; proprietary SaaS", _MT_SUB, D),
            "hosting": Fact("AWS, US and Ireland data centres; GDPR, ISO 27001 certified, "
                            "WCAG 2.1/2.2 AA", _MT_COMPL, D),
            "pricing": Fact("Annual subscription priced by organisation size (three tiers), or a "
                            "fixed 12-month single project; quote only", _MT_SUB, D),
            "free": Fact("Two-week sandbox, free, cannot publish a live project", _MT_SUB, D),
            "public_results": Fact("Public project pages and auto-updating reports on the "
                                   "Communicate tier and above; none on the entry tier", _MT_SUB, D),
            "onboarding": Fact("Talk to sales or book a demo; onboarding included", _MT_SUB, D),
            "languages": Fact("Multilingual questionnaires with a built-in translation tool and "
                              "AI translation; count not published", _MT_SUB, D),
        },
    ),
    Vendor(
        key="partimap", name="PARTIMAP", maker="K-Monitor, Budapest", url=_PM_HOME,
        category="ppgis",
        summary="A free, open-source map survey tool from a Hungarian transparency NGO: points, "
                "lines and areas on a multilingual interface, exports to spreadsheet and KML.",
        facts={
            "geometry": Fact("Points, lines and areas", _PM_TERMS, D),
            "export": Fact("XLSX report; map elements as KML", _PM_TERMS, D),
            "licence": Fact("Yes, GPLv3 on GitHub", _PM_GITHUB, D),
            "hosting": Fact("Operated by K-Monitor in Budapest; residency and GDPR statement not "
                            "published", _PM_HOME, D),
            "pricing": Fact("Free; no subscription or licence fee", _PM_HOME, D),
            "free": Fact("Everything is free", _PM_HOME, D),
            "public_results": Fact(NP, _PM_HOME, D),
            "onboarding": Fact("Self-serve registration", _PM_HOME, D),
            "languages": Fact("Hungarian, English, German, Spanish, Lithuanian, Romanian", _PM_HOME, D),
        },
    ),
    Vendor(
        key="govocal", name="Go Vocal", maker="Go Vocal (formerly CitizenLab), Brussels",
        url="https://www.govocal.com/", category="engagement",
        summary="The participation suite that named the category: project pages, surveys, ideation, "
                "voting and participatory budgeting, with a mapping tool where residents drop pins "
                "and draw lines and polygons.",
        facts={
            "geometry": Fact("Pins, lines and polygons; Shapefile upload for context layers", _GV_MAP, D),
            "export": Fact("'Export all data at any time' and an API; a unified format described "
                           "as importable in GIS tools; file formats not named", _GV_FEAT, D),
            "licence": Fact("Free Edition under AGPLv3 to self-host; the commercial edition is "
                            "SaaS only", _GV_OSS, D),
            "hosting": Fact("UK and EEA on the G-Cloud listing; GDPR, ISO 27001 and WCAG 2.2 AA "
                            "stated", _GV_GCLOUD, D),
            "pricing": Fact("Per licence per year; a rate is listed on UK G-Cloud, otherwise quote",
                            _GV_GCLOUD, D),
            "free": Fact("Free Edition to run yourself; a trial environment through sales", _GV_OSS, D),
            "public_results": Fact("Resident-facing project pages and a report builder", _GV_FEAT, D),
            "onboarding": Fact("Schedule a demo; three-phase onboarding with the vendor", _GV_GCLOUD, D),
            "languages": Fact("27, with automatic translation of residents' input", _GV_FEAT, D),
        },
    ),
    Vendor(
        key="openpoint", name="Open Point (Social Pinpoint)", maker="Open Point, Melbourne",
        url="https://www.openpoint.com/", category="engagement",
        landing_key="social_pinpoint_alternative",
        summary="The engagement hub behind Social Pinpoint, Social Point and MetroQuest: dozens of "
                "tools, among them a Social Map where participants pin a comment and vote on "
                "others' pins.",
        facts={
            "geometry": Fact("Pin a comment on the map; line or polygon drawing not published",
                             _OP_TOOLS, D),
            "export": Fact("XLS, CSV, PDF or GeoJSON from Social Map reporting", _OP_REPORT, D),
            "licence": Fact("No; proprietary SaaS", _OP_TOOLS, D),
            "hosting": Fact("AWS, 'in the nominated country and data centre you live in'; WCAG "
                            "target level AA, VPAT for WCAG 2.2 on request", _OP_FAQ, D),
            "pricing": Fact("By request: a solutions team reviews the project first", _OP_PRICING, D),
            "free": Fact(NP, _OP_PRICING, D),
            "public_results": Fact("Contributions shown publicly on the map; voting in five modes",
                                   _OP_SMAP, D),
            "onboarding": Fact("Book a demo", _OP_TOOLS, D),
            "languages": Fact(NP, _OP_FAQ, D),
        },
        extras=(
            ExtraRow("Engagement-hub extras (forums, voting, budgeting)",
                     "No; focused on map surveys",
                     Fact("Yes: a wide suite of tools, with voting on map contributions in five "
                          "modes", _OP_SMAP, D)),
        ),
    ),
    Vendor(
        key="citizen_space", name="Citizen Space", maker="Delib, Bristol",
        url="https://www.delib.net/citizen_space", category="engagement",
        summary="The default statutory-consultation platform of UK public bodies, with a Geospatial "
                "add-on: pins, routes and areas, validation boundaries, GeoJSON and Shapefile both ways.",
        facts={
            "geometry": Fact("Pins, lines and routes, shapes and polygons; validation areas",
                             _CS_GEO, D),
            "export": Fact("XLSX, DOCX, PDF, JSON, GeoJSON, Shapefile", _CS_GCLOUD, D),
            "licence": Fact("No; proprietary SaaS", _CS_GCLOUD, D),
            "hosting": Fact("UK and EEA, storage location chosen by the customer; ISO 27001; WCAG "
                            "2.1 AA, moving to 2.2", _CS_GCLOUD, D),
            "pricing": Fact("Per instance per year; a rate is listed on UK G-Cloud, otherwise quote",
                            _CS_GCLOUD, D),
            "free": Fact("Time-limited branded sandbox for internal testing", _CS_GCLOUD, D),
            "public_results": Fact("Yes: published respondent data on interactive maps, with "
                                   "moderation and redaction", _CS_GEO, D),
            "onboarding": Fact("Book a demo", _CS_GEO, D),
            "languages": Fact(NP, _CS_GEO, D),
        },
    ),
    Vendor(
        key="commonplace", name="Commonplace", maker="Zencity (acquired Commonplace in 2025)",
        url=_CP_HOME, category="engagement",
        summary="UK planning-engagement platform built around a Community Heatmap: residents drop a "
                "pin and answer a short survey about it; now part of Zencity.",
        facts={
            "geometry": Fact("Pin-drop on the Community Heatmap; line or polygon drawing not "
                             "published", _CP_GCLOUD, D),
            "export": Fact("CSV", _CP_GCLOUD, D),
            "licence": Fact("No; proprietary SaaS", _CP_GCLOUD, D),
            "hosting": Fact("United Kingdom; WCAG 2.1 AA", _CP_GCLOUD, D),
            "pricing": Fact("Per licence; a rate is listed on UK G-Cloud, otherwise quote", _CP_GCLOUD, D),
            "free": Fact("Four-week trial of the basic features; mapping excluded", _CP_GCLOUD, D),
            "public_results": Fact(NP, _CP_HOME, D),
            "onboarding": Fact("Schedule a demo", _CP_HOME, D),
            "languages": Fact(NP, _CP_GCLOUD, D),
        },
    ),
    Vendor(
        key="engagementhq", name="EngagementHQ", maker="Granicus", url=_EHQ_PROD,
        category="engagement",
        summary="Granicus's engagement suite (formerly Bang the Table) with a Places tool: a pin "
                "drop with a photo and a short survey on one of eight map types.",
        facts={
            "geometry": Fact("A pin drop with a photo and a short survey; drawing by participants "
                             "not published", _EHQ_PLACES, D),
            "export": Fact("CSV, Excel, PDF", _EHQ_GCLOUD, D),
            "licence": Fact("No; proprietary SaaS", _EHQ_GCLOUD, D),
            "hosting": Fact("'Regional hosting to meet data governance needs worldwide'; United "
                            "Kingdom on the G-Cloud listing; WCAG 2.2 AA", _EHQ_GCLOUD, D),
            "pricing": Fact("A rate is listed on UK G-Cloud, otherwise quote", _EHQ_GCLOUD, D),
            "free": Fact("'Limited trial subject to scoping'", _EHQ_GCLOUD, D),
            "public_results": Fact(NP, _EHQ_PROD, D),
            "onboarding": Fact("Book a demo", _EHQ_PROD, D),
            "languages": Fact(NP, _EHQ_GCLOUD, D),
        },
    ),
    Vendor(
        key="metroquest", name="MetroQuest", maker="MetroQuest, Vancouver (Social Pinpoint since 2023)",
        url="https://metroquest.com/", category="engagement", landing_key="metroquest_alternative",
        summary="The visual five-screen survey built for transport planning, with a map-marker "
                "screen; acquired by Social Pinpoint in July 2023 and sold on annual subscription.",
        facts={
            "geometry": Fact("Map markers on an interactive map screen; drawing not published",
                             _MQ_TXDOT, D),
            "export": Fact(NP, _MQ_PROD, D),
            "licence": Fact("No; proprietary SaaS", _MQ_PROD, D),
            "hosting": Fact("Not published; the tool itself is described as not ADA accessible, "
                            "with PDF and Word versions offered instead", _MQ_TXDOT, D),
            "pricing": Fact("Annual subscription; 'Get Pricing' form, no rate published", _MQ_PROD, D),
            "free": Fact("Not published; sample surveys to try", _MQ_PRICING, D),
            "public_results": Fact(NP, _MQ_PROD, D),
            "onboarding": Fact("Pricing form; six weeks' lead time to build a survey reported by "
                               "TxDOT", _MQ_TXDOT, D),
            "languages": Fact("English plus one additional language by manual translation", _MQ_TXDOT, D),
        },
        extras=(
            ExtraRow("Status", "Active, open source",
                     Fact("Acquired by Social Pinpoint on 12 July 2023, to be integrated into "
                          "its suite", _OP_MQ_ACQ, D)),
            ExtraRow("Post-launch edits", "Yes, draft and publish versioning",
                     Fact("'MetroQuest surveys cannot be edited after they are launched'", _MQ_TXDOT, D)),
            ExtraRow("Survey structure", "Unlimited sections and questions",
                     Fact("Five screens per survey from 14 templates; Welcome and Wrap Up required",
                          _MQ_TXDOT, D)),
        ),
    ),
    Vendor(
        key="survey123", name="ArcGIS Survey123", maker="Esri", url=_S123_OVERVIEW,
        category="field",
        summary="Esri's form-centric field app: geopoint, geotrace and geoshape questions that land "
                "in ArcGIS Online or Enterprise feature layers, offline, with the whole Esri stack behind it.",
        facts={
            "geometry": Fact("Point (geopoint), line (geotrace) and polygon (geoshape), or one "
                             "Map question", _S123_TYPES, D),
            "export": Fact("CSV, Excel, KML, Shapefile, File Geodatabase from the Data page",
                           _S123_EXPORT, D),
            "licence": Fact("No; proprietary, included with ArcGIS Online or Enterprise", _S123_OVERVIEW, D),
            "hosting": Fact("ArcGIS Online region chosen at purchase: United States, EU or "
                            "Asia-Pacific", _S123_REGIONS, D),
            "pricing": Fact("Included with an ArcGIS Online or Enterprise subscription; rates not "
                            "on the product page", _S123_OVERVIEW, D),
            "free": Fact("21-day trial", _S123_OVERVIEW, D),
            "public_results": Fact("Publicly shared surveys can be answered without signing in; "
                                   "results in web maps and dashboards", _S123_OVERVIEW, D),
            "onboarding": Fact("Sign up for the trial yourself, or contact sales", _S123_OVERVIEW, D),
            "languages": Fact("Multilingual surveys; count not published", _S123_OVERVIEW, D),
        },
    ),
    Vendor(
        key="kobotoolbox", name="KoboToolbox", maker="Kobo Inc. (non-profit)",
        url="https://www.kobotoolbox.org/", category="field",
        summary="The humanitarian sector's open-source data-collection platform: point, line and "
                "area questions, a free Community plan, and an EU server for residency.",
        facts={
            "geometry": Fact("Point (geopoint), line (geotrace) and area (geoshape); only points "
                             "show on the built-in map", _KOBO_GPS, D),
            "export": Fact("CSV, XLS, GeoJSON (points, lines, polygons), KML (points only)", _KOBO_GPS, D),
            "licence": Fact("Yes, AGPL-3.0 on GitHub", _KOBO_GITHUB, D),
            "hosting": Fact("Global server, or an EU server hosted in Ireland and Germany; DPA "
                            "for EU organisations", _KOBO_GDPR, D),
            "pricing": Fact("Free Community plan; paid plans by submission volume, rates listed on "
                            "the site", _KOBO_PLANS, D),
            "free": Fact("Community plan: 5,000 submissions a month and 1 GB of storage, "
                         "automatic after sign-up", _KOBO_PLANS, D),
            "public_results": Fact(NP, _KOBO_ACCOUNT, D),
            "onboarding": Fact("Self-serve account on the server of your choice", _KOBO_ACCOUNT, D),
            "languages": Fact(NP, _KOBO_ACCOUNT, D),
        },
    ),
    Vendor(
        key="merginmaps", name="Mergin Maps", maker="Lutra Consulting", url=_MM_HOME,
        category="field",
        summary="QGIS in the field: your QGIS project and forms on a phone, points, lines and "
                "polygons captured offline and synced; open-source Community Edition to self-host.",
        facts={
            "geometry": Fact("Points, lines and polygons with QGIS-built forms, offline", _MM_FEATURES, D),
            "export": Fact("Not published on the pages read; data lives in the QGIS project",
                           _MM_FEATURES, D),
            "licence": Fact("Yes, open-source Community Edition on GitHub for self-hosting", _MM_PRICING, D),
            "hosting": Fact("Cloud service; 'choice of data residency' on the Enterprise plan; "
                            "GDPR statement not on the pricing page", _MM_PRICING, D),
            "pricing": Fact("Per contributor per month, rates listed on the site; Enterprise by "
                            "quote", _MM_PRICING, D),
            "free": Fact("14-day trial; free Academic and Non-Profit plans; Community Edition "
                         "self-hosted", _MM_PRICING, D),
            "public_results": Fact("Publish a QGIS project online and share it by URL", _MM_HOME, D),
            "onboarding": Fact("Self-serve 'Start for free'", _MM_HOME, D),
            "languages": Fact(NP, _MM_HOME, D),
        },
    ),
    Vendor(
        key="decidim", name="Decidim", maker="Decidim Association, Barcelona", url=_DC_HOME,
        category="open_source",
        summary="The Barcelona-born participatory-democracy framework: processes, proposals, "
                "assemblies and participatory budgeting; a proposal's address is geocoded to a map pin.",
        facts={
            "geometry": Fact("A proposal or meeting address geocoded to a point on a map; drawing "
                             "not published", _DC_MAPS, D),
            "export": Fact("Proposals as CSV, JSON and Excel, with address and coordinates since "
                           "release 0.26", _DC_EXPORT, D),
            "licence": Fact("Yes, AGPL-3.0; Ruby on Rails, you install it", _DC_GITHUB, D),
            "hosting": Fact("Self-hosted, so wherever you put it; map tiles and geocoding from "
                            "HERE, an OpenStreetMap-based provider or your own servers", _DC_MAPS, D),
            "pricing": Fact("Free software; hosting partners are not priced on the site", _DC_HOME, D),
            "free": Fact("Everything is free; the cost is running it", _DC_HOME, D),
            "public_results": Fact("Public participation site with accountability and results "
                                   "modules", _DC_FEAT, D),
            "onboarding": Fact("Install it yourself ('First steps') or through a partner", _DC_HOME, D),
            "languages": Fact("Twelve listed on the features page, community-translated", _DC_FEAT, D),
        },
    ),
    Vendor(
        key="consul", name="Consul Democracy", maker="Consul Democracy Foundation", url=_CD_HOME,
        category="open_source",
        summary="The Madrid-born open-source platform for proposals, debates, voting and "
                "participatory budgeting; with geolocation on, residents place a proposal on a map.",
        facts={
            "geometry": Fact("A proposal placed as a point on the map when geolocation is "
                             "enabled; drawing not published", _CD_ADMIN, D),
            "export": Fact(NP, _CD_ADMIN, D),
            "licence": Fact("Yes, AGPL v3; you install it", _CD_GITHUB, D),
            "hosting": Fact("Self-hosted, so wherever you put it; certified partners offer "
                            "implementation", _CD_HOME, D),
            "pricing": Fact("Free to use and modify; partner services not priced on the site", _CD_HOME, D),
            "free": Fact("Everything is free; the cost is running it", _CD_HOME, D),
            "public_results": Fact("Public participation site with voting and participatory "
                                   "budgeting", _CD_HOME, D),
            "onboarding": Fact("Install it yourself or through a certified partner", _CD_HOME, D),
            "languages": Fact(NP, _CD_HOME, D),
        },
    ),
    Vendor(
        key="jotform", name="Jotform", maker="Jotform Inc.", url="https://www.jotform.com/",
        category="forms",
        summary="A general form builder whose Geolocation widget captures one location per "
                "response as a draggable Google Maps pin, address or coordinates.",
        facts={
            "geometry": Fact("One location per response: a draggable pin, address or coordinates "
                             "(Google Maps API key required); no drawing", _JF_GEO, D),
            "export": Fact("CSV, Excel, PDF", _JF_EXPORT, D),
            "licence": Fact("No; proprietary SaaS", _JF_PRICING, D),
            "hosting": Fact("GDPR and CCPA support; data residency on the Enterprise plan only",
                            _JF_PRICING, D),
            "pricing": Fact("Per plan per month, rates listed on the site; Enterprise by quote", _JF_PRICING, D),
            "free": Fact("Starter plan: 5 forms and 100 submissions a month, with Jotform branding",
                         _JF_PRICING, D),
            "public_results": Fact(NP, _JF_PRICING, D),
            "onboarding": Fact("Self-serve sign-up", _JF_PRICING, D),
            "languages": Fact(NP, _JF_PRICING, D),
        },
    ),
    Vendor(
        key="google_forms", name="Google Forms", maker="Google", url=_GF_PROD, category="forms",
        summary="The form everyone already has: twelve question types, none of them a map, with "
                "responses in a Google Sheet.",
        facts={
            "geometry": Fact("No map or location question type; an address is typed as text",
                             _GF_TYPES, D),
            "export": Fact("Responses to a linked Google Sheet", _GF_RESP, D),
            "licence": Fact("No; proprietary SaaS", _GF_PROD, D),
            "hosting": Fact(NP, _GF_PROD, D),
            "pricing": Fact("Part of Google Workspace; plan rates on a separate pricing page", _GF_PROD, D),
            "free": Fact(NP, _GF_PROD, D),
            "public_results": Fact(NP, _GF_PROD, D),
            "onboarding": Fact("Self-serve with a Google account", _GF_PROD, D),
            "languages": Fact(NP, _GF_PROD, D),
        },
    ),
)

_BY_KEY = {v.key: v for v in VENDORS}
_BY_LANDING = {v.landing_key: v for v in VENDORS if v.landing_key}


def get_vendor(key: str) -> Vendor:
    return _BY_KEY[key]


def vendor_for_landing(landing_key: str):
    """The vendor an `/alternatives/` page is about, or None for every other landing."""
    return _BY_LANDING.get(landing_key)


def vendors_in(category_key: str):
    return [v for v in VENDORS if v.category == category_key]


def compare_rows(vendor: Vendor):
    """Criteria rows for a two-column 'Mapsurvey vs <vendor>' table, then the vendor's extras."""
    rows = [{"label": c.label, "ours": MAPSURVEY.facts[c.key].text, "theirs": vendor.facts[c.key]}
            for c in CRITERIA]
    rows += [{"label": e.label, "ours": e.ours, "theirs": e.theirs} for e in vendor.extras]
    return rows


def hub_context():
    """Everything `/participatory-mapping-tools/` renders, precomputed so the template loops only."""
    return {
        "criteria": CRITERIA,
        "categories": [{"category": c, "vendors": vendors_in(c.key)} for c in CATEGORIES],
        "vendors": VENDORS,
        "mapsurvey": MAPSURVEY,
    }


def _validate():
    today = date.today().isoformat()
    for v in VENDORS:
        if v.category not in _CATEGORY_KEYS:
            raise ValueError(f"vendors.py: {v.key} names unknown category {v.category!r}")
        missing = [k for k in _CRITERION_KEYS if k not in v.facts]
        if missing:
            raise ValueError(f"vendors.py: {v.key} lacks facts for {missing}")
        for f in list(v.facts.values()) + [e.theirs for e in v.extras]:
            if not f.source.startswith("https://"):
                raise ValueError(f"vendors.py: {v.key}: fact {f.text!r} has no https source")
            try:
                date.fromisoformat(f.verified)
            except ValueError:
                raise ValueError(f"vendors.py: {v.key}: bad verified date {f.verified!r}")
            if f.verified > today:
                raise ValueError(f"vendors.py: {v.key}: verified date {f.verified} is in the future")
    if len(_BY_KEY) != len(VENDORS):
        raise ValueError("vendors.py: duplicate vendor key")


_validate()

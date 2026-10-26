"""The Mapsurvey brand as search engines should read it (change brand-entity, #443).

Google answers the query "mapsurvey" with our brand page only part of the time; otherwise it reads
the name as "survey map". The JSON-LD built here tells it that Mapsurvey is one organisation, one
web application and one site, all at mapsurvey.org, and links that organisation to the profiles we
own elsewhere.

PROFILES is the one list of those profiles. Add a URL here when a listing goes live (Wikidata,
LinkedIn, a directory) and nowhere else; only profiles we control belong here, because sameAs
tells search engines the two pages are the same entity.
"""
from django.conf import settings
from django.templatetags.static import static

SITE_URL = "https://mapsurvey.org/"
ORGANIZATION_ID = SITE_URL + "#organization"
SOFTWARE_ID = SITE_URL + "#software"
WEBSITE_ID = SITE_URL + "#website"

NAME = "Mapsurvey"
ALTERNATE_NAMES = ["mapsurvey.org", "Mapsurvey.org"]
DESCRIPTION = (
    "Open-source participatory-mapping platform: map-based surveys where participants mark "
    "places, draw routes, and outline areas."
)

PROFILES = [
    "https://www.wikidata.org/wiki/Q141878840",
    "https://participedia.net/method/mapsurvey-1",
]


def same_as():
    """Profiles for Organization.sameAs: the public repository first, then the registry."""
    urls = []
    repo = getattr(settings, "GITHUB_REPO_URL", "")
    for url in ([repo] if repo else []) + PROFILES:
        if url not in urls:
            urls.append(url)
    return urls


def organization():
    return {
        "@type": "Organization",
        "@id": ORGANIZATION_ID,
        "name": NAME,
        "alternateName": ALTERNATE_NAMES,
        "url": SITE_URL,
        "logo": SITE_URL.rstrip("/") + static("favicon-512x512.png"),
        "description": DESCRIPTION,
        "sameAs": same_as(),
    }


def software():
    node = {
        "@type": "SoftwareApplication",
        "@id": SOFTWARE_ID,
        "name": NAME,
        "url": SITE_URL,
        "applicationCategory": "BusinessApplication",
        "applicationSubCategory": "Participatory mapping and map-based surveys",
        "operatingSystem": "Any (web browser)",
        "description": DESCRIPTION,
        "isAccessibleForFree": True,
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD",
            "description": "Free plan on mapsurvey.org; free to self-host under the AGPL",
        },
        "license": "https://www.gnu.org/licenses/agpl-3.0.html",
        "publisher": {"@id": ORGANIZATION_ID},
        "author": {"@id": ORGANIZATION_ID},
    }
    repo = getattr(settings, "GITHUB_REPO_URL", "")
    if repo:
        node["codeRepository"] = repo
    return node


def website():
    return {
        "@type": "WebSite",
        "@id": WEBSITE_ID,
        "name": NAME,
        "alternateName": ALTERNATE_NAMES,
        "url": SITE_URL,
        "publisher": {"@id": ORGANIZATION_ID},
    }

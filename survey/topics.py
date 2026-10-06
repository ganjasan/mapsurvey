"""Story topics: the controlled vocabulary that ties a story to the landing page it proves.

One registry (change story-topics, issue #250). A topic is a slug, a label and, when the
page exists, the key of the SEO landing in ``seo_landings.SEO_LANDINGS`` it belongs to. A
topic without a landing is allowed on purpose: it marks demand for a page (epic #257), and
its chip renders as plain text until the page exists.

Why a registry and not free text: a tag only earns a link when it means exactly one page.
``seed_story`` and the admin both refuse a slug that is not here, so "community-engagement"
cannot drift into "community_engagement" on one story and link to nothing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    label: str
    landing_key: str = ""   # key in seo_landings.SEO_LANDINGS, or "" when no page exists yet


TOPICS = (
    # Category pages (the B2G money terms).
    Topic("community-engagement", "Community engagement", "community_engagement_platform"),
    Topic("public-consultation", "Public consultation", "public_consultation_software"),
    Topic("civic-engagement", "Civic engagement", "civic_engagement"),
    Topic("participatory-budgeting", "Participatory budgeting", "participatory_budgeting"),
    # Audience pages.
    Topic("urban-planning", "Urban planning", "for_planners"),
    Topic("local-government", "Local government", "for_government"),
    Topic("research", "Research", "for_researchers"),
    Topic("education", "Education", "for_educators"),
    Topic("consultants", "Consultants", "for_consultants"),
    # No page yet -- each is a candidate landing in epic #257.
    Topic("citizen-engagement", "Citizen engagement"),
    Topic("neighbourhood-plan", "Neighbourhood plans"),
    Topic("parks-public-space", "Parks and public space"),
    Topic("transport-cycling", "Transport and cycling"),
    Topic("citizen-science", "Citizen science"),
)

_BY_SLUG = {t.slug: t for t in TOPICS}
_BY_LANDING = {t.landing_key: t for t in TOPICS if t.landing_key}
assert len(_BY_LANDING) == sum(1 for t in TOPICS if t.landing_key), "a landing page belongs to one topic"


def by_slug(slug: str):
    """The Topic for ``slug``, or None."""
    return _BY_SLUG.get(slug)


def for_landing(landing_key: str):
    """The Topic whose page is the landing ``landing_key``, or None (alternatives pages)."""
    return _BY_LANDING.get(landing_key)


def validate_slugs(slugs) -> list:
    """Return ``slugs`` as a list, or raise ValueError naming the first unknown one."""
    if not isinstance(slugs, (list, tuple)):
        raise ValueError("topics must be a list of topic slugs")
    for slug in slugs:
        if slug not in _BY_SLUG:
            raise ValueError(
                f"Unknown story topic {slug!r}; known: {', '.join(_BY_SLUG)}")
    return list(slugs)


def chips_for(story):
    """(label, landing path or '') for each of the story's topics, in the story's order."""
    from .seo_landings import get_landing

    chips = []
    for slug in story.topics or []:
        topic = _BY_SLUG.get(slug)
        if topic is None:
            continue    # a slug removed from the registry: show nothing rather than break the page
        chips.append((topic.label, get_landing(topic.landing_key).path if topic.landing_key else ""))
    return chips


def stories_for(topic, queryset=None):
    """Published stories carrying ``topic`` (a Topic or a slug), in showcase order."""
    from .models import Story

    slug = topic.slug if isinstance(topic, Topic) else topic
    queryset = Story.objects.filter(is_published=True) if queryset is None else queryset
    return Story.in_showcase_order(queryset.filter(topics__contains=[slug]))

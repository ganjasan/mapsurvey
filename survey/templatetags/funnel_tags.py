"""Template tags for embedding the creator-funnel dashboard outside its
changelist page (currently: the admin index). See survey/funnel.py."""

from django import template

from ..funnel import dashboard_context

register = template.Library()


@register.inclusion_tag("admin/_funnel_content.html")
def funnel_dashboard_content():
    """Render the full funnel dashboard body (queries run per call)."""
    return dashboard_context()

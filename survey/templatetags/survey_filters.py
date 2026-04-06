from django import template

register = template.Library()

STATUS_BADGE_CLASSES = {
    'draft': 'secondary',
    'testing': 'warning',
    'published': 'success',
    'closed': 'info',
    'archived': 'dark',
}


@register.filter
def status_badge_class(status):
    return STATUS_BADGE_CLASSES.get(status, 'secondary')


@register.filter
def cover_gradient(name):
    """Generate a deterministic gradient CSS from a string."""
    h = hash(name or '') % 360
    return f'linear-gradient(135deg, hsl({h}, 55%, 50%), hsl({(h + 40) % 360}, 45%, 40%))'


LINT_DESCRIPTIONS = {
    'self_intersection': 'Polygon has self-intersecting geometry',
    'empty_required': 'Required question was not answered',
    'out_of_range': 'Value is outside the allowed min/max range',
    'numeric_outlier': 'Value is a statistical outlier (>3σ from mean)',
    'short_text': 'Text answer is suspiciously short',
    'area_outlier': 'Polygon area is much larger or smaller than typical',
}


@register.filter
def lint_tooltip(lint_list):
    """Convert a list of lint codes to human-readable tooltip text."""
    if not lint_list:
        return ''
    return '; '.join(LINT_DESCRIPTIONS.get(code, code) for code in lint_list)

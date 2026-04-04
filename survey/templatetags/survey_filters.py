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

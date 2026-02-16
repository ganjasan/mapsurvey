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

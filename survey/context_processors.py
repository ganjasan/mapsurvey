from django.conf import settings


def mapbox(request):
    return {
        'MAPBOX_URL': settings.MAPBOX_URL,
        'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
    }


def contact(request):
    return {
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL', ''),
        'CONTACT_TELEGRAM': getattr(settings, 'CONTACT_TELEGRAM', ''),
    }

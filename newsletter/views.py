from django.db.models import F
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import CampaignRecipient, NewsletterPreference

TRACKING_PIXEL = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00'
    b'\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def unsubscribe_confirm(request, token):
    preference = get_object_or_404(NewsletterPreference, unsubscribe_token=token)

    if request.method == 'POST':
        preference.unsubscribe()
        return render(request, 'newsletter/unsubscribe_done.html')

    return render(request, 'newsletter/unsubscribe_confirm.html', {
        'preference': preference,
    })


@csrf_exempt
def unsubscribe_one_click(request, token):
    """RFC 8058 one-click unsubscribe (POST only)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    preference = get_object_or_404(NewsletterPreference, unsubscribe_token=token)
    preference.unsubscribe()
    return HttpResponse(status=200)


@require_GET
def track_open(request, campaign_id, user_id):
    """Record email open and return 1x1 transparent GIF."""
    try:
        updated = CampaignRecipient.objects.filter(
            campaign_id=campaign_id,
            user_id=user_id,
            opened_at__isnull=True,
        ).update(opened_at=timezone.now())

        if updated:
            from .models import Campaign
            Campaign.objects.filter(pk=campaign_id).update(
                total_opened=F('total_opened') + 1,
            )
    except Exception:
        pass

    response = HttpResponse(TRACKING_PIXEL, content_type='image/gif')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response['Pragma'] = 'no-cache'
    return response

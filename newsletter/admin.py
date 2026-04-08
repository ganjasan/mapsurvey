from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import path

from .forms import TestSendForm
from .models import BounceRecord, Campaign, CampaignRecipient, NewsletterPreference
from .tasks import send_campaign_chunk


class CampaignRecipientInline(admin.TabularInline):
    model = CampaignRecipient
    extra = 0
    readonly_fields = ('user', 'status', 'sent_at', 'opened_at', 'error_message')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'total_sent', 'total_opened', 'recipient_count_display', 'created_at', 'sent_at')
    list_filter = ('status',)
    readonly_fields = ('status', 'total_sent', 'total_opened', 'cursor_user_id', 'sent_at', 'created_by')
    fields = ('subject', 'preheader', 'body_html', 'status', 'created_by', 'sent_at', 'total_sent', 'total_opened', 'cursor_user_id')
    inlines = [CampaignRecipientInline]
    change_form_template = 'newsletter/admin/campaign_change_form.html'

    def recipient_count_display(self, obj):
        return obj.get_recipient_count()
    recipient_count_display.short_description = 'Recipients'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/preview/', self.admin_site.admin_view(self.preview_view), name='newsletter_campaign_preview'),
            path('<int:pk>/test-send/', self.admin_site.admin_view(self.test_send_view), name='newsletter_campaign_test_send'),
            path('<int:pk>/send/', self.admin_site.admin_view(self.send_view), name='newsletter_campaign_send'),
        ]
        return custom_urls + urls

    def preview_view(self, request, pk):
        from .email_renderer import _personalize
        campaign = get_object_or_404(Campaign, pk=pk)
        html = render_to_string('newsletter/email_campaign.html', {
            'body_html': _personalize(campaign.body_html, request.user),
            'preheader': campaign.preheader,
            'unsubscribe_url': '#',
            'pixel_url': '',
            'physical_address': settings.NEWSLETTER_PHYSICAL_ADDRESS,
        })
        return HttpResponse(html)

    def test_send_view(self, request, pk):
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        campaign = get_object_or_404(Campaign, pk=pk)
        form = TestSendForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': form.errors}, status=400)

        from django.contrib.auth import get_user_model
        from .email_renderer import render_campaign_email
        User = get_user_model()

        # Use request user as the recipient context
        preference, _ = NewsletterPreference.objects.get_or_create(user=request.user)

        msg = render_campaign_email(campaign, request.user, preference)
        msg.to = [form.cleaned_data['email']]
        try:
            msg.send()
            return JsonResponse({'success': True, 'message': f'Test email sent to {form.cleaned_data["email"]}'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def send_view(self, request, pk):
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        # Atomic check-and-set to prevent double-dispatch
        updated = Campaign.objects.filter(pk=pk, status='draft').update(
            status='sending',
            cursor_user_id=0,
            total_sent=0,
            total_opened=0,
        )
        if not updated:
            return JsonResponse({'error': 'Campaign is not in draft status'}, status=400)

        campaign = get_object_or_404(Campaign, pk=pk)
        send_campaign_chunk.delay(campaign.pk)
        recipient_count = campaign.get_recipient_count()
        messages.success(request, f'Campaign "{campaign.subject}" is being sent to {recipient_count} recipients.')
        return JsonResponse({'success': True, 'message': f'Sending to {recipient_count} recipients'})

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            campaign = Campaign.objects.get(pk=object_id)
            extra_context['recipient_count'] = campaign.get_recipient_count()
            extra_context['can_send'] = campaign.can_send()
        return super().changeform_view(request, object_id, form_url, extra_context)


class NewsletterPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_unsubscribed', 'unsubscribed_at')
    list_filter = ('is_unsubscribed',)
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('unsubscribe_token',)


class CampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'user', 'status', 'sent_at', 'opened_at')
    list_filter = ('campaign', 'status')
    search_fields = ('user__email',)
    readonly_fields = ('campaign', 'user', 'status', 'sent_at', 'opened_at', 'error_message')

    def has_add_permission(self, request):
        return False


class BounceRecordAdmin(admin.ModelAdmin):
    list_display = ('email', 'bounce_type', 'received_at')
    list_filter = ('bounce_type',)
    search_fields = ('email',)
    readonly_fields = ('email', 'bounce_type', 'received_at', 'raw_payload')

    def has_add_permission(self, request):
        return False


admin.site.register(Campaign, CampaignAdmin)
admin.site.register(NewsletterPreference, NewsletterPreferenceAdmin)
admin.site.register(CampaignRecipient, CampaignRecipientAdmin)
admin.site.register(BounceRecord, BounceRecordAdmin)

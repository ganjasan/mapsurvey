import json

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import BillingEvent, CheckoutIntent, ProHelpRequest, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('organization', 'product_key', 'status', 'current_period_end', 'renewal_type',
                    'ppg_subscription_id', 'needs_review', 'superseded_at', 'updated_at')
    list_filter = ('status', 'product_key', 'renewal_type', 'needs_review')
    search_fields = ('organization__name', 'organization__slug', 'ppg_subscription_id', 'customer_email',
                     'ppg_initial_order_id', 'ppg_last_order_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('organization',)
    actions = ('mark_reviewed',)

    @admin.action(description='Mark chargeback reviewed (clears the flag; access is not restored)')
    def mark_reviewed(self, request, queryset):
        queryset.update(needs_review=False)


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ('received_at', 'ipn_type_name', 'order_id', 'ppg_subscription_id', 'organization',
                    'test_mode', 'is_resent', 'ignored_test', 'error')
    list_filter = ('ipn_type_id', 'test_mode', 'ignored_test', 'error')
    search_fields = ('order_id', 'ppg_subscription_id', 'organization__name', 'payload')
    readonly_fields = [f.name for f in BillingEvent._meta.fields] + ['payload_pretty']
    exclude = ('payload',)
    raw_id_fields = ('organization', 'subscription')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Payload')
    def payload_pretty(self, obj):
        return format_html('<pre style="white-space:pre-wrap">{}</pre>', json.dumps(obj.payload, indent=1, sort_keys=True))


@admin.register(CheckoutIntent)
class CheckoutIntentAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'organization', 'user', 'product_key', 'quote', 'consumed_at', 'order_id', 'nonce')
    list_filter = ('product_key', 'quote')
    search_fields = ('organization__name', 'nonce', 'order_id', 'user__email')
    raw_id_fields = ('organization', 'user')


@admin.register(ProHelpRequest)
class ProHelpRequestAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'organization', 'kind', 'survey', 'contact_email', 'handled_at')
    list_filter = ('kind',)
    search_fields = ('organization__name', 'contact_email', 'message')
    raw_id_fields = ('organization', 'user', 'survey')
    actions = ('mark_handled',)

    @admin.action(description='Mark handled')
    def mark_handled(self, request, queryset):
        queryset.filter(handled_at__isnull=True).update(handled_at=timezone.now())

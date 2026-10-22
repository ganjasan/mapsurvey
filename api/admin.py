"""Read-only: staff see labels, kinds and dates. The token column holds a hash
and the value exists only in the one-time response the creator saw."""
from django.contrib import admin

from .models import TokenProfile


@admin.register(TokenProfile)
class TokenProfileAdmin(admin.ModelAdmin):
    list_display = ('token_id', 'kind', 'label', 'user', 'organization', 'created_at', 'last_used_at', 'revoked_at')
    list_filter = ('kind',)
    search_fields = ('label', 'token__user__username', 'token__user__email')
    readonly_fields = ('token', 'kind', 'label', 'suffix', 'audiences', 'organization', 'revoked_at',
                       'last_used_at', 'created_by_ip', 'created_at')
    ordering = ('-created_at',)

    @admin.display(description='user')
    def user(self, obj):
        return obj.token.user

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

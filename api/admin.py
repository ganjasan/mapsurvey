"""Staff views of the token table and the client registry.

`TokenProfile` is read-only: the token column holds a hash and the value
exists only in the one-time response the creator saw. `Application` is where
first-party clients are made (change oauth-server, D8): the pre_save hook in
`api.apps` holds the admin to the same redirect rules as DCR and CIMD.
"""
from django.contrib import admin
from django.db.models import Count
from oauth2_provider.admin import ApplicationAdmin as DotApplicationAdmin
from oauth2_provider.models import Application

from .models import TokenProfile


@admin.register(TokenProfile)
class TokenProfileAdmin(admin.ModelAdmin):
    list_display = ('token_id', 'kind', 'label', 'user', 'organization', 'created_at', 'last_used_at', 'revoked_at')
    list_filter = ('kind',)
    search_fields = ('label', 'token__user__username', 'token__user__email')
    readonly_fields = ('token', 'kind', 'label', 'suffix', 'audiences', 'organization', 'revoked_at',
                       'last_used_at', 'created_by_ip', 'created_at', 'code_checksum')
    ordering = ('-created_at',)

    @admin.display(description='user')
    def user(self, obj):
        return obj.token.user

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.unregister(Application)


@admin.register(Application)
class ApplicationAdmin(DotApplicationAdmin):
    list_display = ('name', 'client_id_short', 'registration_source', 'client_type', 'skip_authorization',
                    'created', 'grants', 'refresh_tokens')
    list_filter = ('registration_source', 'client_type', 'skip_authorization')
    search_fields = ('name', 'client_id', 'redirect_uris')
    ordering = ('-created',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            n_grants=Count('grant', distinct=True),
            n_refresh=Count('refreshtoken', distinct=True),
        )

    @admin.display(description='client id')
    def client_id_short(self, obj):
        return obj.client_id if len(obj.client_id) <= 48 else obj.client_id[:45] + '…'

    @admin.display(description='codes', ordering='n_grants')
    def grants(self, obj):
        return obj.n_grants

    @admin.display(description='refresh tokens', ordering='n_refresh')
    def refresh_tokens(self, obj):
        return obj.n_refresh

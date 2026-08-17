from django import forms
from django.contrib.gis import admin as gisadmin
from django.contrib import admin, messages
from django.contrib.admin import helpers as admin_helpers
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.shortcuts import render
from .models import (
    Organization, SurveyHeader, SurveySection, Question, Answer,
    SurveySession,
    SurveySectionTranslation, QuestionTranslation,
    Story, FunnelReport, SignupAttribution, AuditLog,
    Cohort, CohortDimension, UserCohort, DomainSegmentRule,
    CreatorNote, CreatorProfile,
    PublicResultsPage, PublicResultsBlock,
    AIGenerationEvent,
)
from .funnel import dashboard_context
from leaflet.admin import LeafletGeoAdmin


class SurveySectionTranslationInline(admin.TabularInline):
    model = SurveySectionTranslation
    extra = 1
    fields = ('language', 'title', 'subheading')


class QuestionTranslationInline(admin.TabularInline):
    model = QuestionTranslation
    extra = 1
    fields = ('language', 'name', 'subtext')


class SurveyAdmin(LeafletGeoAdmin):
    list_display = ('organization', 'name', 'visibility', 'is_archived', 'redirect_url', 'available_languages')
    list_filter = ('visibility', 'is_archived')


class QuestionInLine(admin.TabularInline):
    model = Question
    fields = ('parent_question_id', 'name', 'subtext', 'order_number', 'input_type', 'choices', 'required', 'color', 'icon_class', 'image')


class SurveySectionAdmin(LeafletGeoAdmin):
    list_display = ('name', 'title', 'is_head', 'code', 'survey_header', 'subheading', 'start_map_postion', 'start_map_zoom')

    inlines = [
        SurveySectionTranslationInline,
        QuestionInLine,
    ]


class QuestionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'input_type', 'survey_section')
    inlines = [
        QuestionTranslationInline,
    ]


gisadmin.site.register(Organization)
gisadmin.site.register(SurveyHeader, SurveyAdmin)
gisadmin.site.register(SurveySection, SurveySectionAdmin)
gisadmin.site.register(Question, QuestionAdmin)
admin.site.register(SurveySession)
admin.site.register(Answer)


class StoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'story_type', 'is_published', 'published_date')
    list_filter = ('story_type', 'is_published')
    prepopulated_fields = {'slug': ('title',)}


admin.site.register(Story, StoryAdmin)


@admin.register(SignupAttribution)
class SignupAttributionAdmin(admin.ModelAdmin):
    list_display = ('user', 'utm_source', 'source_bucket', 'utm_campaign', 'created_at')
    list_filter = ('source_bucket', 'utm_source')
    search_fields = ('user__username', 'utm_source', 'utm_campaign', 'raw_referrer')
    readonly_fields = ('created_at',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only viewer for the append-only audit trail (design D4)."""

    list_display = ('created_at', 'action', 'survey_name', 'actor', 'ip')
    list_filter = ('action',)
    search_fields = ('survey_name', 'survey_uuid', 'actor__username', 'ip')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CohortInline(admin.TabularInline):
    model = Cohort
    extra = 1
    fields = ('name', 'slug', 'order', 'color', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CohortDimension)
class CohortDimensionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'cohort_count')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CohortInline]

    @admin.display(description='Cohorts')
    def cohort_count(self, obj):
        return obj.cohorts.count()


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ('name', 'dimension', 'slug', 'order', 'assigned_users')
    list_filter = ('dimension',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='Users')
    def assigned_users(self, obj):
        return obj.assignments.count()


@admin.register(DomainSegmentRule)
class DomainSegmentRuleAdmin(admin.ModelAdmin):
    """Domain -> segment rules. Deliberately not in source: the repo is public."""

    list_display = ('domain', 'cohort', 'note')
    list_filter = ('cohort',)
    search_fields = ('domain', 'note')
    autocomplete_fields = ('cohort',)


@admin.register(UserCohort)
class UserCohortAdmin(admin.ModelAdmin):
    list_display = ('user', 'dimension', 'cohort', 'source', 'assigned_at')
    list_filter = ('dimension', 'cohort', 'source')
    search_fields = ('user__username', 'user__email', 'note')
    readonly_fields = ('dimension', 'assigned_at')
    autocomplete_fields = ('user',)


class AssignCohortForm(forms.Form):
    """Cohort picker for the bulk action on the user changelist."""

    cohort = forms.ModelChoiceField(
        queryset=Cohort.objects.select_related('dimension').order_by(
            'dimension__order', 'order', 'name',
        ),
        label='Assign cohort',
        help_text='Replaces any existing assignment in the same dimension. '
                  'Analytical label only — it grants no access.',
    )
    note = forms.CharField(required=False, max_length=255)


class CohortMembershipInline(admin.TabularInline):
    model = UserCohort
    extra = 0
    fk_name = 'user'
    fields = ('cohort', 'source', 'note', 'assigned_at')
    readonly_fields = ('assigned_at',)
    verbose_name_plural = 'Cohorts (analytical labels only)'


class CreatorProfileInline(admin.StackedInline):
    model = CreatorProfile
    extra = 0
    can_delete = True
    fields = (
        ('organization', 'role'), ('country', 'how_found_us'),
        ('linkedin_url', 'website'), 'summary',
    )
    verbose_name_plural = 'Creator profile (staff-only, never shown to the user)'


class CreatorNoteInline(admin.TabularInline):
    model = CreatorNote
    fk_name = 'user'
    extra = 0
    fields = ('happened_on', 'kind', 'body', 'author', 'source_path')
    readonly_fields = ('source_path',)
    ordering = ('-happened_on', '-id')
    verbose_name_plural = 'Notes (append-only: add new ones, do not rewrite history)'


class UserAdmin(DjangoUserAdmin):
    """Django's user admin plus cohorts, the creator dossier and a bulk assign action."""

    inlines = [CreatorProfileInline, CohortMembershipInline, CreatorNoteInline]
    list_display = DjangoUserAdmin.list_display + ('organization', 'cohort_labels')
    actions = ['assign_cohort_action']

    @admin.display(description='Cohorts')
    def cohort_labels(self, obj):
        return ', '.join(
            a.cohort.name for a in obj.cohorts.all().select_related('cohort')
        ) or '—'

    @admin.display(description='Organisation')
    def organization(self, obj):
        profile = getattr(obj, 'creator_profile', None)
        return (profile.organization if profile else '') or '—'

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related('creator_profile')
                .prefetch_related('cohorts__cohort'))

    @admin.action(description='Assign a cohort to selected users')
    def assign_cohort_action(self, request, queryset):
        from .cohorts import assign_cohort

        if 'apply' in request.POST:
            form = AssignCohortForm(request.POST)
            if form.is_valid():
                cohort = form.cleaned_data['cohort']
                note = form.cleaned_data['note']
                for user in queryset:
                    assign_cohort(user, cohort, source='manual', note=note)
                self.message_user(
                    request,
                    f'Assigned "{cohort}" to {queryset.count()} user(s).',
                    messages.SUCCESS,
                )
                return None
        else:
            form = AssignCohortForm()

        return render(request, 'admin/assign_cohort.html', {
            'title': 'Assign a cohort',
            'users': queryset,
            'form': form,
            'action_checkbox_name': admin_helpers.ACTION_CHECKBOX_NAME,
        })


@admin.register(CreatorNote)
class CreatorNoteAdmin(admin.ModelAdmin):
    """Cross-user reading of the timeline: what did we learn, and when."""

    list_display = ('happened_on', 'user', 'kind', 'author', 'excerpt')
    list_filter = ('kind', 'happened_on')
    search_fields = ('user__username', 'user__email', 'body', 'source_path')
    date_hierarchy = 'happened_on'
    autocomplete_fields = ('user', 'author')

    @admin.display(description='Note')
    def excerpt(self, obj):
        text = ' '.join(obj.body.split())
        return text[:110] + ('…' if len(text) > 110 else '')


@admin.register(CreatorProfile)
class CreatorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'country', 'updated_at')
    list_filter = ('country',)
    search_fields = ('user__username', 'user__email', 'organization', 'role', 'summary')
    autocomplete_fields = ('user',)


User = get_user_model()
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(FunnelReport)
class FunnelDashboardAdmin(admin.ModelAdmin):
    """Staff-only creator acquisition->activation funnel dashboard.

    Renders CreatorFunnelService aggregates via a custom changelist template. The
    proxy model carries no data; the queryset is emptied so the ChangeList stays cheap.
    See openspec/changes/funnel-monitoring/design.md (D1).
    """

    change_list_template = "admin/funnel_dashboard.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def get_queryset(self, request):
        # No rows needed -- the whole view is aggregate data injected below.
        return super().get_queryset(request).none()

    def changelist_view(self, request, extra_context=None):
        # Period selector for the weekly charts: ?weeks=12|26 (default 26; "all" = None).
        raw = request.GET.get("weeks", "26")
        try:
            weeks = None if raw == "all" else max(1, int(raw))
        except (TypeError, ValueError):
            weeks, raw = 26, "26"
        # Strip our custom param so the admin ChangeList doesn't treat it as an
        # unknown filter lookup (which would redirect to ?e=1).
        if "weeks" in request.GET:
            mutable = request.GET.copy()
            del mutable["weeks"]
            request.GET = mutable
        extra_context = extra_context or {}
        extra_context["title"] = "Growth funnel"
        extra_context["weeks_sel"] = raw
        extra_context.update(dashboard_context(weeks=weeks))
        return super().changelist_view(request, extra_context=extra_context)


class PublicResultsBlockInline(admin.TabularInline):
    model = PublicResultsBlock
    extra = 0
    fields = ('order', 'block_type', 'question', 'viz', 'is_hidden')


class PublicResultsPageAdmin(admin.ModelAdmin):
    list_display = ('slug', 'survey', 'visibility', 'is_published', 'mode', 'frozen_at')
    list_filter = ('visibility', 'is_published', 'mode')
    inlines = [PublicResultsBlockInline]


admin.site.register(PublicResultsPage, PublicResultsPageAdmin)


@admin.register(AIGenerationEvent)
class AIGenerationEventAdmin(admin.ModelAdmin):
    """Read-only viewer for LLM generation attempts (cost, quality, failures)."""

    # `total_latency_ms` and `attempts` sit next to `latency_ms` on purpose:
    # read alone, a large latency does not say whether the model was slow or
    # the draft was retried, and that is the first question a spike raises.
    list_display = ('created_at', 'kind', 'outcome', 'user', 'organization',
                    'provider', 'model', 'attempts', 'latency_ms', 'total_latency_ms',
                    'input_tokens', 'output_tokens', 'thinking_tokens')
    list_filter = ('kind', 'outcome', 'provider')
    search_fields = ('user__username', 'organization__name', 'error_detail')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

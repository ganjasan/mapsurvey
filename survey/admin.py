from django.contrib.gis import admin as gisadmin
from django.contrib import admin
from .models import (
    Organization, SurveyHeader, SurveySection, Question, Answer,
    SurveySession,
    SurveySectionTranslation, QuestionTranslation,
    Story, FunnelReport,
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
        extra_context = extra_context or {}
        extra_context["title"] = "Funnel dashboard"
        extra_context.update(dashboard_context())
        return super().changelist_view(request, extra_context=extra_context)


# Admin home shows the funnel dashboard above the app list
# (survey/templates/admin/funnel_index.html extends the stock admin/index.html).
admin.site.index_template = "admin/funnel_index.html"

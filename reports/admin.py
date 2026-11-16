from django.contrib import admin

from reports.models import Report, ReportBlock


class ReportBlockInline(admin.TabularInline):
    model = ReportBlock
    extra = 0
    fields = ('order', 'block_type', 'dataset', 'question_code', 'viz', 'is_hidden')
    raw_id_fields = ('dataset',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('slug', 'organization', 'survey', 'visibility', 'is_published', 'mode', 'frozen_at')
    list_filter = ('visibility', 'is_published', 'mode')
    search_fields = ('slug',)
    raw_id_fields = ('organization', 'survey', 'created_by')
    inlines = [ReportBlockInline]

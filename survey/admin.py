from django.contrib.gis import admin as gisadmin
from django.contrib import admin
from .models import (
    Organization, SurveyHeader, SurveySection, Question, Answer,
    SurveySession,
    SurveySectionTranslation, QuestionTranslation,
)
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
    list_display = ('organization', 'name', 'redirect_url', 'available_languages')


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

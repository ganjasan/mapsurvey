from django.contrib.gis import admin as gisadmin
from django.contrib import admin
from .models import Organization, SurveyHeader, SurveySection, Question, Answer, OptionGroup, OptionChoice, SurveySession
from leaflet.admin import LeafletGeoAdmin

class SurveyAdmin(LeafletGeoAdmin):
	list_display = ('organization','name', 'redirect_url')

class QuestionInLine(admin.TabularInline):
	model = Question
	fields = ('parent_question_id','name', 'subtext','order_number','input_type','option_group', 'required', 'color', 'icon_class', 'image')

class SurveySectionAdmin(LeafletGeoAdmin):
	list_display = ('name', 'title', 'is_head', 'code', 'survey_header', 'subheading', 'start_map_postion', 'start_map_zoom')

	inlines = [
		QuestionInLine,
	]



gisadmin.site.register(Organization)
gisadmin.site.register(SurveyHeader, SurveyAdmin)
gisadmin.site.register(SurveySection, SurveySectionAdmin)
gisadmin.site.register(Question)
admin.site.register(OptionGroup)
admin.site.register(OptionChoice)
admin.site.register(SurveySession)
admin.site.register(Answer)


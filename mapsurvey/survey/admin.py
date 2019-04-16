from django.contrib.gis import admin as gisadmin
from django.contrib import admin
from .models import Organization, SurveyHeader, SurveySection, Question, Answer, OptionGroup, OptionChoice, SurveySession
from leaflet.admin import LeafletGeoAdmin

class SurveyAdmin(LeafletGeoAdmin):
	list_display = ('organization','name', 'title', 'instructions', 'redirect_url', 'start_map_postion', 'start_map_zoom')

class QuestionInLine(admin.TabularInline):
	model = Question

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

'''
class QuestionAdmin(LeafletGeoAdmin):
	list_display = ('survey', 'is_head', 'code', 'map_position', 'zoom', 'title', 'description', 'next_question', 'prev_question')



admin.site.register(Survey, SurveyAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(InputType)
admin.site.register(User)
admin.site.register(Answer)
admin.site.register(SurveySession)
'''



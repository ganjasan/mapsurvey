from django.contrib.gis import admin
from .models import Question
from leaflet.admin import LeafletGeoAdmin

'''
class QuestionAdmin(LeafletGeoAdmin):
	list_display = ('survey', 'is_head', 'code', 'map_position', 'zoom', 'title', 'description', 'next_question', 'prev_question')

class SurveyAdmin(LeafletGeoAdmin):
	list_display = ('name', 'url_name', 'description', 'pub_date', 'map_position', 'zoom', 'first_question')

admin.site.register(Survey, SurveyAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(InputType)
admin.site.register(User)
admin.site.register(Answer)
admin.site.register(SurveySession)
'''

admin.site.register(Question)
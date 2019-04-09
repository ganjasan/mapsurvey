from django.db import models
from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import Point
from datetime import datetime

DEFAULT_SURVEY_ID = 1

class Organization(models.Model):
    name = models.CharField(max_length=250)

class User(models.Model):
    username = models.CharField(max_length=80)

class Survey(models.Model):
    name = models.CharField(max_length=50)
    url_name = models.CharField(max_length=50, default='survey')
    description = models.TextField()
    pub_date = models.DateTimeField('date published')
    map_position = geomodels.PointField(null=True, blank=True)
    zoom = models.IntegerField(default=12)
    author = models.CharField(max_length=250, default="No author")
    first_question = models.ForeignKey("Question", on_delete=models.SET_NULL, related_name="survey_first_question", null=True, blank=True)


    def __str__(self):
        return self.name

class SurveySession(models.Model):
    survey = models.ForeignKey("Survey", on_delete=models.CASCADE)
    session_start_datetime = models.DateTimeField(null=False, blank=False, default=datetime.now)
    session_end_datetime = models.DateTimeField(null=True, blank=True)

class InputType(models.Model):
    name = models.CharField(max_length=80)

    def __str__(self):
        return self.name

class Question(models.Model):
    survey = models.ForeignKey("Survey", on_delete = models.CASCADE, default=DEFAULT_SURVEY_ID)
    input_type = models.ForeignKey("InputType", on_delete=models.SET_NULL, null=True, blank=True)

    is_head = models.BooleanField(default=False)
    code = models.CharField(max_length=50, blank=False, unique=True, default="blank_question")
    title = models.CharField(max_length=50, default="Blank Question")
    description = models.TextField(default="Blank Question")

    map_position = geomodels.PointField(null=True, blank=True)
    zoom = models.IntegerField(default=12)
    
    next_question = models.ForeignKey("Question", on_delete=models.SET_NULL, null=True, related_name="survey_next_question", blank=True)
    prev_question = models.ForeignKey("Question", on_delete=models.SET_NULL, null=True, related_name='survey_prev_question', blank=True)

    def __str__(self):
        return self.survey.name+"_"+self.code

class Answer(models.Model):
    #user = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, blank=True)
    survey_session =  models.ForeignKey("SurveySession", on_delete=models.CASCADE)
    question = models.ForeignKey("Question", on_delete=models.CASCADE)

    numeric = models.FloatField(null=True,blank=True)
    text = models.TextField(null=True, blank=True)
    yn = models.BooleanField(null=True, blank=True) #yes-no
    point = geomodels.PointField(null=True, blank=True)
    line = geomodels.LineStringField(null=True, blank=True)
    polygon = geomodels.PolygonField(null=True, blank=True)





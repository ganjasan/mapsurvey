from django.db import models
from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import Point
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q



INPUT_TYPE_CHOICES = (
    ("text", _("Text")),
    ("radio", _("Multiple Choices")),
    ("checbox", _("Checkboxes")),
    ("rating", _("Rating")),
    ("datetime", _("Date/Time")),
    ("point", _("Geo Point")),
    ("line", _("Geo Line")),
    ("polygon", _("Geo Polygon")),
)

#organizations
#example - QULLAB
class Organization(models.Model):
    name = models.CharField(max_length=250)

    def __str__(self):
        return self.name

#survey headers
#example - quality of urban life 
class SurveyHeader(models.Model):
    organization = models.ForeignKey("Organization", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=45, unique=True)
    title = models.CharField(max_length=80, null=True, blank=True)
    instructions = models.TextField(blank=True, null=True)
    redirect_url = models.CharField(max_length=250, default="#") #URL to redirect to when survey is complete.

    def __str__(self):
        return self.title

    def start_section(self):
        if not hasattr(self, "__sscache"):
            self.__sscache = SurveySections.objects.get(Q(questionnaire=self) & Q(is_head=True))
        return self.__sscache



#survey sections
class SurveySections(models.Model):
    is_head = models.BooleanField(default=False)

    survey_header = models.ForeignKey("SurveyHeader", on_delete=models.CASCADE)
    name = models.CharField(max_length=45, default="main_section") #section_a
    title = models.CharField(max_length=80, null=True, blank=True) #Your Home Area
    subheading = models.CharField(max_length=4096, null=True, blank=True) #Several question about your home area quality

    def __str__(self):
        return self.title

#examples - Never-Always, Years-By-Five
class OptionGroup(models.Model):
    name = models.CharField(max_length=45)

    def __str__(self):
        return self.name

class Question(models.Model):
    survey_section = models.ForeignKey("SurveySections", on_delete=models.CASCADE)
    code = models.CharField(max_length=8) #Q1 - using as url path and sort field
    name = models.CharField(max_length=80, null=True, blank=True)
    subtext = models.CharField(max_length=500, null=True, blank=True)
    input_type = models.CharField(max_length=80, choices=INPUT_TYPE_CHOICES)
    option_group = models.ForeignKey("OptionGroup", on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

class OptionChoice(models.Model):
    option_group = models.ForeignKey("OptionGroup", on_delete=models.CASCADE)
    choice_name = models.CharField(max_length=45)
    sort_id = models.IntegerField(null=True, blank=True) #for options sorting

class QuestionOption(models.Model):
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    option_choice = models.ForeignKey("OptionChoice", on_delete=models.CASCADE)

class Answer(models.Model):
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    question_option = models.ForeignKey("QuestionOption", on_delete=models.CASCADE, null=True, blank=True)

    numeric = models.FloatField(null=True,blank=True)
    text = models.TextField(null=True, blank=True)
    yn = models.BooleanField(null=True, blank=True) #yes-no
    point = geomodels.PointField(null=True, blank=True)
    line = geomodels.LineStringField(null=True, blank=True)
    polygon = geomodels.PolygonField(null=True, blank=True)


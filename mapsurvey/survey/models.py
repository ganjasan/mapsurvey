from django.db import models
from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import Point
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q



INPUT_TYPE_CHOICES = (
    ("text", _("Text")),
    ("number", _("Number")),
    ("choice", _("Choices")),
    ("multichoice", _("Multiple Choices")),
    ("rating", _("Rating")),
    ("datetime", _("Date/Time")),
    ("point", _("Geo Point")),
    ("line", _("Geo Line")),
    ("polygon", _("Geo Polygon")),
)

class SurveySession(models.Model):
    survey = models.ForeignKey("SurveyHeader", on_delete=models.CASCADE)
    start_datetime = models.DateTimeField(default=datetime.now)
    end_datetime = models.DateTimeField(null=True, blank=True)

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

    start_map_postion = geomodels.PointField(default='POINT(0.0 0.0)')
    start_map_zoom = models.IntegerField(default=12)

    def __str__(self):
        return self.title

    def start_section(self):
        if not hasattr(self, "__sscache"):
            self.__sscache = SurveySection.objects.get(Q(survey_header=self) & Q(is_head=True))
        return self.__sscache

    def questions(self):
        if not hasattr(self, "__qcache"):
            self.__sscache = Question.objects.filter(survey_section__in=SurveySection.objects.filter(survey_header=self))
        return self.__sscache

    def geo_questions(self):
        if not hasattr(self, "__gqcache"):
            self.__sscache = Question.objects.filter(Q(survey_section__in=SurveySection.objects.filter(survey_header=self)) & Q(input_type__in=['point','line','polygon']))
        return self.__sscache

    def answers(self):
        if not hasattr(self, "__gqcache"):
            self.__sscache = Answer.objects.filter(Q(question__in=Question.objects.filter(survey_section__in=SurveySection.objects.filter(survey_header=self))))
        return self.__sscache

#survey sections
class SurveySection(models.Model):
    is_head = models.BooleanField(default=False)

    survey_header = models.ForeignKey("SurveyHeader", on_delete=models.CASCADE)
    name = models.CharField(max_length=45, default="main_section") #section_a
    title = models.CharField(max_length=80, null=True, blank=True) #Your Home Area
    subheading = models.CharField(max_length=4096, null=True, blank=True) #Several question about your home area quality
    code = models.CharField(max_length=8)

    start_map_postion = geomodels.PointField(default='POINT(0.0 0.0)')
    start_map_zoom = models.IntegerField(default=12)

    next_section = models.ForeignKey("SurveySection", null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_next_section')
    prev_section = models.ForeignKey("SurveySection", null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_prev_section')

    def __str__(self):
        return self.name

    def questions(self):
        if not hasattr(self, "__qcache"):
            self.__qcache = Question.objects.filter(survey_section=self).order_by('code')
        return self.__qcache



#examples - Never-Always, Years-By-Five
class OptionGroup(models.Model):
    name = models.CharField(max_length=45, unique=True)
    #choices = models.ManyToManyField("OptionChoice")

    def __str__(self):
        return self.name

    def choices(self):
        if not hasattr(self, "__ccache"):
            self.__ccache = OptionChoice.objects.filter(option_group=self).order_by('code')
        return self.__ccache

class OptionChoice(models.Model):
    option_group = models.ForeignKey("OptionGroup", on_delete=models.CASCADE)
    name = models.CharField(max_length=45)
    code = models.IntegerField(null=False, blank=False)

    def __str__(self):
        return self.name

class Question(models.Model):
    survey_section = models.ForeignKey("SurveySection", on_delete=models.CASCADE)
    code = models.CharField(max_length=8) #Q1 - using as url path and sort field
    name = models.CharField(max_length=80, null=True, blank=True)
    subtext = models.CharField(max_length=500, null=True, blank=True)
    input_type = models.CharField(max_length=80, choices=INPUT_TYPE_CHOICES)
    option_group = models.ForeignKey("OptionGroup", on_delete=models.CASCADE, null=True)
    required = models.BooleanField(default=False)
    color = models.CharField(verbose_name=_(u'Color'), max_length=7, help_text=_(u'HEX color, as #RRGGBB'), default="#F1F1F1")

    def __str__(self):
        return self.name

    def answers(self):
        if not hasattr(self, "__acache"):
            self.__acache = Answer.objects.filter(question=self)
        return self.__acache



'''
class QuestionOption(models.Model):
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    option_choice = models.ForeignKey("OptionChoice", on_delete=models.CASCADE)
'''

class Answer(models.Model):
    survey_session = models.ForeignKey("SurveySession", on_delete=models.CASCADE)
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    choice = models.ManyToManyField("OptionChoice")

    numeric = models.FloatField(null=True,blank=True)
    text = models.TextField(null=True, blank=True)
    yn = models.BooleanField(null=True, blank=True) #yes-no
    point = geomodels.PointField(null=True, blank=True)
    line = geomodels.LineStringField(null=True, blank=True)
    polygon = geomodels.PolygonField(null=True, blank=True)


from django.db import models
from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import Point
from datetime import datetime
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import random

#VALIDATORS
url_name_validator = RegexValidator(
    regex = r'[a-zA-Z0-9_]',
    message=_('Only alphanumeric character and "_" sign'),
    code='invalid',
)

def validate_url_name(value):
    return url_name_validator(value)


INPUT_TYPE_CHOICES = (
    ("text", _("Text")),
    ("number", _("Number")),
    ("choice", _("Choices")),
    ("multichoice", _("Multiple Choices")),
    ("range", _("Range")),
    ("rating", _("Rating")),
    ("datetime", _("Date/Time")),
    ("point", _("Geo Point")),
    ("line", _("Geo Line")),
    ("polygon", _("Geo Polygon")),
    ("image", _("Image")),
    ("text_line", _("Line")),
    ("html", _("HTML")),
)

class SurveySession(models.Model):
    survey = models.ForeignKey("SurveyHeader", on_delete=models.CASCADE)
    start_datetime = models.DateTimeField(default=datetime.now)
    end_datetime = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'survey'

    def answers(self):
        if not hasattr(self, "__acache"):
            self.__acache = Answer.objects.filter(Q(survey_session=self) & Q(parent_answer_id__isnull=True))
        return self.__acache

#organizations
#example - QULLAB
class Organization(models.Model):
    name = models.CharField(max_length=250)
    
    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name

#survey headers
#example - quality of urban life 
class SurveyHeader(models.Model):
    organization = models.ForeignKey("Organization", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=45, unique=True, validators=[validate_url_name])
    redirect_url = models.CharField(max_length=250, default="#", help_text=_('URL to redirect after survey completion. E.g.: /thanks/ or https://example.com'))

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name

    def start_section(self):
        if not hasattr(self, "__sscache"):
            try:
                self.__sscache = SurveySection.objects.get(Q(survey_header=self) & Q(is_head=True))
            except Exception as e:
                self.__sscache = None
        return self.__sscache

    def questions(self):
        if not hasattr(self, "__qcache"):
            self.__qcache = Question.objects.filter(survey_section__in=SurveySection.objects.filter(survey_header=self))
        return self.__qcache

    def geo_questions(self):
        if not hasattr(self, "__gqcache"):
            self.__gqcache = Question.objects.filter(Q(survey_section__in=SurveySection.objects.filter(survey_header=self)) & Q(input_type__in=['point','line','polygon']))
        return self.__gqcache

    def sessions(self):
        if not hasattr(self, "__scache"):
            self.__scache = SurveySession.objects.filter(survey=self)
        return self.__scache

    def answers(self):
        if not hasattr(self, "__acache"):
            self.__acache = Answer.objects.filter(Q(question__in=Question.objects.filter(survey_section__in=SurveySection.objects.filter(survey_header=self))))
        return self.__acache

#survey sections
class SurveySection(models.Model):
    is_head = models.BooleanField(default=False)

    survey_header = models.ForeignKey("SurveyHeader", on_delete=models.CASCADE)
    name = models.CharField(max_length=45, default="survey_description", validators=[validate_url_name]) #section_a
    title = models.CharField(max_length=256, null=True, blank=True) #Your Home Area
    subheading = models.CharField(max_length=4096, null=True, blank=True) #Several question about your home area quality
    code = models.CharField(max_length=8)

    start_map_postion = geomodels.PointField(default='POINT(30.317 59.945)')
    start_map_zoom = models.IntegerField(default=12)

    next_section = models.ForeignKey("SurveySection", null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_next_section')
    prev_section = models.ForeignKey("SurveySection", null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_prev_section')

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name

    def questions(self):
        if not hasattr(self, "__qcache"):
            self.__qcache = Question.objects.filter(survey_section=self).filter(parent_question_id__isnull=True).order_by('order_number')
        return self.__qcache


#examples - Never-Always, Years-By-Five
class OptionGroup(models.Model):
    name = models.CharField(max_length=45, unique=True)
    #choices = models.ManyToManyField("OptionChoice")

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name

    def choices(self):
        if not hasattr(self, "__ccache"):
            self.__ccache = OptionChoice.objects.filter(option_group=self).order_by('code')
        return self.__ccache

class OptionChoice(models.Model):
    option_group = models.ForeignKey("OptionGroup", on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    code = models.IntegerField(null=False, blank=False)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name

def question_code_generator():
    while True:
        code = "Q_"+str(random.random())[2:12]
        try:
            Question.objects.get(code=code)
        except:
            return code

class Question(models.Model):    
    survey_section = models.ForeignKey("SurveySection", on_delete=models.CASCADE)
    parent_question_id = models.ForeignKey('self', default=None, null=True, blank=True, on_delete=models.CASCADE)
    code = models.CharField(max_length=50, default=question_code_generator)
    order_number = models.IntegerField(default=0) # unique in section or popup
    name = models.CharField(max_length=512, null=True, blank=True)
    subtext = models.CharField(max_length=512, null=True, blank=True)
    input_type = models.CharField(max_length=80, choices=INPUT_TYPE_CHOICES)
    option_group = models.ForeignKey("OptionGroup", on_delete=models.CASCADE, null=True)
    required = models.BooleanField(default=False)
    color = models.CharField(verbose_name=_(u'Color'), max_length=7, help_text=_(u'HEX color, as #RRGGBB'), default="#000000")
    icon_class = models.CharField(default="", max_length=80, help_text=_(u'Must be Font-Awesome class'), blank=True, null=True)
    image = models.ImageField(upload_to ='images/', null=True, blank=True)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name 

    def subQuestions(self):
    	if not hasattr(self, "__sqcache"):
    		self.__sqcache = Question.objects.filter(parent_question_id=self).order_by('order_number')
    	return self.__sqcache

    def answers(self):
        if not hasattr(self, "__acache"):
            self.__acache = Answer.objects.filter(question=self)
        return self.__acache

class Answer(models.Model):
    survey_session = models.ForeignKey("SurveySession", on_delete=models.CASCADE)
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    parent_answer_id = models.ForeignKey('self', default=None, null=True, blank=True, on_delete=models.CASCADE)
    choice = models.ManyToManyField("OptionChoice")

    numeric = models.FloatField(null=True,blank=True)
    text = models.TextField(null=True, blank=True)
    yn = models.BooleanField(null=True, blank=True) #yes-no
    point = geomodels.PointField(null=True, blank=True)
    line = geomodels.LineStringField(null=True, blank=True)
    polygon = geomodels.PolygonField(null=True, blank=True)

    class Meta:
        app_label = 'survey'
    
    def subAnswers(self):
    	if not hasattr(self, "__sacache"):
    		subanswers = Answer.objects.filter(parent_answer_id=self)
    		subquestions = self.question.subQuestions()
    		self.__sacache = {}
    		for subquestion in subquestions:
    			self.__sacache[subquestion] = list(filter(lambda a: a.question == subquestion, subanswers))
    	return self.__sacache


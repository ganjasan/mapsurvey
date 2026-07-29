import uuid as uuid_module

from django.conf import settings
from django.db import models
from django.contrib.gis.db import models as geomodels
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, BaseValidator
from django.utils.text import slugify
from django.contrib.auth.hashers import make_password, check_password as django_check_password
import random


ORG_ROLE_CHOICES = (
    ("owner", _("Owner")),
    ("admin", _("Admin")),
    ("editor", _("Editor")),
    ("viewer", _("Viewer")),
)

SURVEY_ROLE_CHOICES = (
    ("owner", _("Owner")),
    ("editor", _("Editor")),
    ("viewer", _("Viewer")),
)


class ChoicesValidator(BaseValidator):
    """Validate that Question.choices JSONField has correct structure."""
    message = "Invalid choices structure."
    code = "invalid_choices"

    def __init__(self, limit_value=None):
        super().__init__(limit_value=limit_value or True)

    def __call__(self, value):
        if not isinstance(value, list):
            raise ValidationError("choices must be a list")
        for item in value:
            if not isinstance(item, dict):
                raise ValidationError("Each choice must be a dict")
            if "code" not in item:
                raise ValidationError("Each choice must have 'code'")
            if "name" not in item:
                raise ValidationError("Each choice must have 'name'")

    def compare(self, a, b):
        return False

#VALIDATORS
url_name_validator = RegexValidator(
    regex = r'[a-zA-Z0-9_]',
    message=_('Only alphanumeric character and "_" sign'),
    code='invalid',
)

def validate_url_name(value):
    return url_name_validator(value)


STATUS_CHOICES = (
    ("draft", _("Draft")),
    ("testing", _("Testing")),
    ("published", _("Published")),
    ("closed", _("Closed")),
    ("archived", _("Archived")),
)

def default_basemaps():
    return ['streets', 'satellite', 'topo']


BASEMAP_CHOICES = [
    ('streets', _('Streets')),
    ('satellite', _('Satellite')),
    ('topo', _('Topo')),
]

VALID_TRANSITIONS = {
    "draft": ["testing", "published"],
    "testing": ["draft", "published"],
    "published": ["closed"],
    "closed": ["published", "archived"],
    "archived": [],
}

VISIBILITY_CHOICES = (
    ("private", _("Private")),
    ("demo", _("Demo")),
    ("public", _("Public")),
)

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
    ("text_line", _("Single Line Text")),
    ("html", _("HTML")),
)

DISPLAY_STYLE_CHOICES = (
    ("default", _("Survey default")),
    ("scale_strip", _("Compact scale")),
    ("list_pips", _("Labeled list")),
)

VALIDATION_STATUS_CHOICES = (
    ('', 'No status'),
    ('approved', 'Approved'),
    ('not_approved', 'Not approved'),
    ('on_hold', 'On hold'),
)


class SurveySessionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class SurveySession(models.Model):
    survey = models.ForeignKey("SurveyHeader", on_delete=models.PROTECT)
    start_datetime = models.DateTimeField(default=datetime.now)
    end_datetime = models.DateTimeField(null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True, help_text=_('Selected language code (ISO 639-1)'))
    validation_status = models.CharField(
        max_length=15, blank=True, default='',
        choices=VALIDATION_STATUS_CHOICES, db_index=True,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(default='', blank=True)

    objects = SurveySessionQuerySet.as_manager()

    class Meta:
        app_label = 'survey'

    def answers(self):
        if not hasattr(self, "__acache"):
            self.__acache = Answer.objects.filter(Q(survey_session=self) & Q(parent_answer_id__isnull=True))
        return self.__acache

EVENT_TYPE_CHOICES = (
    ('session_start',   'Session Start'),
    ('section_view',    'Section View'),
    ('section_submit',  'Section Submit'),
    ('survey_complete', 'Survey Complete'),
    ('page_load',       'Page Load'),
    ('page_leave',      'Page Leave'),
)


class SurveyEvent(models.Model):
    """Append-only event log for respondent behavior tracking."""
    session = models.ForeignKey(
        'SurveySession', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='events',
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'survey'
        indexes = [
            models.Index(fields=['session', 'event_type']),
            models.Index(fields=['session', 'created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} @ {self.created_at} (session {self.session_id})'


class TrackedLink(models.Model):
    """Saved tracking links with UTM parameters for a survey."""
    survey = models.ForeignKey('SurveyHeader', on_delete=models.CASCADE, related_name='tracked_links')
    utm_source = models.CharField(max_length=100)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'survey'
        ordering = ['-created_at']

    def __str__(self):
        parts = [self.utm_source]
        if self.utm_medium:
            parts.append(self.utm_medium)
        if self.utm_campaign:
            parts.append(self.utm_campaign)
        return ' / '.join(parts)

    def build_url(self, request=None):
        """Return full survey URL with UTM params."""
        from urllib.parse import urlencode
        params = {'utm_source': self.utm_source}
        if self.utm_medium:
            params['utm_medium'] = self.utm_medium
        if self.utm_campaign:
            params['utm_campaign'] = self.utm_campaign
        path = f'/surveys/{self.survey.uuid}/?{urlencode(params)}'
        if request is not None:
            return request.build_absolute_uri(path)
        return path


class Organization(models.Model):
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:100] or 'org'
            slug = base_slug
            counter = 2
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix = f'-{counter}'
                slug = base_slug[:100 - len(suffix)] + suffix
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=ORG_ROLE_CHOICES, default='viewer')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'survey'
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user.username} - {self.organization.name} ({self.role})"


class Invitation(models.Model):
    email = models.EmailField()
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='invitations')
    role = models.CharField(max_length=10, choices=ORG_ROLE_CHOICES, default='viewer')
    token = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'survey'

    @property
    def is_expired(self):
        return (timezone.now() - self.created_at).days > 7

    @property
    def is_acceptable(self):
        return not self.accepted_at and not self.is_expired

    def __str__(self):
        return f"{self.email} → {self.organization.name} ({self.role})"

class SurveyHeader(models.Model):
    uuid = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    organization = models.ForeignKey("Organization", on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_surveys')
    name = models.CharField(max_length=45, validators=[validate_url_name])
    redirect_url = models.CharField(max_length=250, default="#", help_text=_('URL to redirect after survey completion. E.g.: /thanks/ or https://example.com'))
    available_languages = models.JSONField(default=list, blank=True, help_text=_('List of ISO 639-1 language codes, e.g. ["en", "ru", "de"]'))
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="private", help_text=_('Controls whether survey appears on the landing page'))
    is_archived = models.BooleanField(default=False, help_text=_('Marks completed surveys whose results can be shown'))
    thanks_html = models.JSONField(default=dict, blank=True, help_text=_('Custom HTML for thanks page. Dict keyed by language: {"en": "<h1>Thanks!</h1>", "ru": "<h1>Спасибо!</h1>"} or a plain string.'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    test_token = models.UUIDField(default=uuid_module.uuid4, unique=True)
    cover_image = models.ImageField(upload_to='covers/', null=True, blank=True)
    validation_settings = models.JSONField(default=dict, blank=True, help_text=_('Survey-level validation thresholds: {fast_threshold_seconds, duplicate_window_hours}'))
    basemaps = models.JSONField(default=default_basemaps, blank=True, help_text=_('Enabled basemaps for respondent map. List from: ["streets", "satellite", "topo"]'))
    default_basemap = models.CharField(max_length=20, null=True, blank=True, choices=BASEMAP_CHOICES, help_text=_('Default basemap shown to respondents. If null, first from basemaps list.'))
    start_map_postion = geomodels.PointField(null=True, blank=True, help_text=_('Default map position for the survey. Sections inherit this if not overridden.'))
    start_map_zoom = models.IntegerField(null=True, blank=True, help_text=_('Default map zoom for the survey. Sections inherit this if not overridden.'))
    use_geolocation = models.BooleanField(default=False, help_text=_('Auto-center map on respondent location when entering the survey.'))
    show_branding = models.BooleanField(default=True, help_text=_('Show a "Made with Mapsurvey" link on the public survey and thanks pages (a free-tier acquisition loop). Turn off for a clean, unbranded look.'))
    style_settings = models.JSONField(default=dict, blank=True, help_text=_('Survey-wide style defaults: {rating_display_style}'))
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text=_('Set when the survey is moved to trash; purged permanently after the retention window.'))

    # Versioning fields
    canonical_survey = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='versions',
        help_text=_('For archived versions, points to the canonical survey')
    )
    version_number = models.PositiveIntegerField(default=1)
    is_canonical = models.BooleanField(default=True, db_index=True)
    published_version = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='draft_copies',
        help_text=_('For draft copies, points to the canonical survey being edited')
    )

    class Meta:
        app_label = 'survey'
        indexes = [
            models.Index(fields=['canonical_survey', '-version_number']),
        ]

    def __str__(self):
        return self.name

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return django_check_password(raw_password, self.password_hash)

    def has_password(self):
        return bool(self.password_hash)

    def clear_password(self):
        self.password_hash = None

    def regenerate_test_token(self):
        self.test_token = uuid_module.uuid4()

    def get_test_url(self, request):
        from django.urls import reverse
        base_url = reverse('survey_header', kwargs={'survey_slug': str(self.uuid)})
        return request.build_absolute_uri(f'{base_url}?token={self.test_token}')

    def get_default_rating_display_style(self):
        value = (self.style_settings or {}).get('rating_display_style')
        return value if value in ('scale_strip', 'list_pips') else 'scale_strip'

    def can_accept_responses(self):
        return self.status in ("testing", "published")

    def can_transition_to(self, new_status):
        valid = VALID_TRANSITIONS.get(self.status, [])
        if new_status not in valid:
            if not valid:
                return False, f"Cannot transition from {self.status}"
            return False, f"Cannot transition from {self.status} to {new_status}"

        if new_status == "testing":
            if not self._has_survey_structure():
                return False, "Survey must have at least one section with questions"
            if not self._has_head_section():
                return False, "Survey must have a head section"

        if new_status == "published" and self.status == "draft":
            if not self._has_survey_structure():
                return False, "Survey must have at least one section with questions"
            if not self._has_head_section():
                return False, "Survey must have a head section"

        return True, ""

    def _has_survey_structure(self):
        sections = SurveySection.objects.filter(survey_header=self)
        if not sections.exists():
            return False
        return Question.objects.filter(survey_section__in=sections).exists()

    def _has_head_section(self):
        return SurveySection.objects.filter(survey_header=self, is_head=True).exists()

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

    def is_multilingual(self):
        return bool(self.available_languages and len(self.available_languages) > 0)

    # Trash (soft-delete) helpers
    TRASH_RETENTION_DAYS = 30

    @property
    def is_trashed(self):
        return self.deleted_at is not None

    @property
    def purge_after(self):
        if self.deleted_at is None:
            return None
        return self.deleted_at + timedelta(days=self.TRASH_RETENTION_DAYS)

    # Versioning methods
    def has_draft_copy(self):
        return self.draft_copies.exists()

    def get_draft_copy(self):
        return self.draft_copies.first()

    @property
    def is_draft_copy(self):
        return self.published_version_id is not None

    def get_version_history(self):
        return SurveyHeader.objects.filter(
            canonical_survey=self, is_canonical=False
        ).order_by('-version_number')


class SurveyCollaborator(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='survey_collaborations')
    survey = models.ForeignKey('SurveyHeader', on_delete=models.CASCADE, related_name='collaborators')
    role = models.CharField(max_length=10, choices=SURVEY_ROLE_CHOICES, default='viewer')

    class Meta:
        app_label = 'survey'
        unique_together = ('user', 'survey')

    def __str__(self):
        return f"{self.user.username} - {self.survey.name} ({self.role})"


#survey sections
class SurveySection(models.Model):
    is_head = models.BooleanField(default=False)

    survey_header = models.ForeignKey("SurveyHeader", on_delete=models.CASCADE)
    name = models.CharField(max_length=45, default="survey_description", validators=[validate_url_name]) #section_a
    title = models.CharField(max_length=256, null=True, blank=True) #Your Home Area
    subheading = models.CharField(max_length=4096, null=True, blank=True) #Several question about your home area quality
    code = models.CharField(max_length=8)

    start_map_postion = geomodels.PointField(null=True, blank=True, help_text=_('Override map position for this section. Null = keep current map position.'))
    start_map_zoom = models.IntegerField(null=True, blank=True, help_text=_('Override map zoom for this section. Null = keep current zoom.'))
    use_geolocation = models.BooleanField(default=False, help_text=_('If true, fly to respondent location when entering this section.'))
    override_basemap = models.CharField(max_length=20, null=True, blank=True, choices=BASEMAP_CHOICES, help_text=_('Override basemap for this section. Null = keep current basemap.'))

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

    def get_translated_title(self, lang):
        if not lang:
            return self.title
        try:
            translation = self.translations.get(language=lang)
            return translation.title if translation.title else self.title
        except SurveySectionTranslation.DoesNotExist:
            return self.title

    def get_translated_subheading(self, lang):
        if not lang:
            return self.subheading
        try:
            translation = self.translations.get(language=lang)
            return translation.subheading if translation.subheading else self.subheading
        except SurveySectionTranslation.DoesNotExist:
            return self.subheading


class SurveySectionTranslation(models.Model):
    section = models.ForeignKey("SurveySection", on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10, help_text=_('ISO 639-1 language code'))
    title = models.CharField(max_length=256, null=True, blank=True)
    subheading = models.CharField(max_length=4096, null=True, blank=True)

    class Meta:
        app_label = 'survey'
        unique_together = ('section', 'language')

    def __str__(self):
        return f"{self.section.name} ({self.language})"


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
    choices = models.JSONField(null=True, blank=True, validators=[ChoicesValidator()])
    required = models.BooleanField(default=False)
    validation_settings = models.JSONField(default=dict, blank=True, help_text=_('Per-question validation: {min_value, max_value, outlier_sigma, min_length, area_outlier_factor}'))
    color = models.CharField(verbose_name=_(u'Color'), max_length=7, help_text=_(u'HEX color, as #RRGGBB'), default="#000000")
    icon_class = models.CharField(default="", max_length=80, help_text=_(u'Must be Font-Awesome class'), blank=True, null=True)
    image = models.ImageField(upload_to ='images/', null=True, blank=True)
    display_style = models.CharField(max_length=20, choices=DISPLAY_STYLE_CHOICES, default="default", help_text=_('Rendering style, only used by rating questions; "default" inherits the survey-wide style'))

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

    def get_translated_name(self, lang):
        if not lang:
            return self.name
        try:
            translation = self.translations.get(language=lang)
            return translation.name if translation.name else self.name
        except QuestionTranslation.DoesNotExist:
            return self.name

    def get_translated_subtext(self, lang):
        if not lang:
            return self.subtext
        try:
            translation = self.translations.get(language=lang)
            return translation.subtext if translation.subtext else self.subtext
        except QuestionTranslation.DoesNotExist:
            return self.subtext

    def get_choice_name(self, code, lang=None):
        for choice in self.choices or []:
            if choice["code"] == code:
                names = choice["name"]
                if isinstance(names, dict):
                    if lang and lang in names:
                        return names[lang]
                    if "en" in names:
                        return names["en"]
                    return next(iter(names.values()))
                return names
        return str(code)


class QuestionTranslation(models.Model):
    question = models.ForeignKey("Question", on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=10, help_text=_('ISO 639-1 language code'))
    name = models.CharField(max_length=512, null=True, blank=True)
    subtext = models.CharField(max_length=512, null=True, blank=True)

    class Meta:
        app_label = 'survey'
        unique_together = ('question', 'language')

    def __str__(self):
        return f"{self.question.code} ({self.language})"


class Answer(models.Model):
    survey_session = models.ForeignKey("SurveySession", on_delete=models.CASCADE)
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    parent_answer_id = models.ForeignKey('self', default=None, null=True, blank=True, on_delete=models.CASCADE)
    selected_choices = models.JSONField(null=True, blank=True)

    numeric = models.FloatField(null=True,blank=True)
    text = models.TextField(null=True, blank=True)
    yn = models.BooleanField(null=True, blank=True) #yes-no
    point = geomodels.PointField(null=True, blank=True)
    line = geomodels.LineStringField(null=True, blank=True)
    polygon = geomodels.PolygonField(null=True, blank=True)

    class Meta:
        app_label = 'survey'
    
    def get_selected_choice_names(self, lang=None):
        codes = self.selected_choices or []
        return [self.question.get_choice_name(code, lang) for code in codes]

    def subAnswers(self):
    	if not hasattr(self, "__sacache"):
    		subanswers = Answer.objects.filter(parent_answer_id=self)
    		subquestions = self.question.subQuestions()
    		self.__sacache = {}
    		for subquestion in subquestions:
    			self.__sacache[subquestion] = list(filter(lambda a: a.question == subquestion, subanswers))
    	return self.__sacache


STORY_TYPE_CHOICES = (
    ("map", _("Map")),
    ("open-data", _("Open Data")),
    ("results", _("Results")),
    ("article", _("Article")),
)


class Story(models.Model):
    title = models.CharField(max_length=256)
    slug = models.SlugField(max_length=256, unique=True)
    body = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='stories/', null=True, blank=True)
    story_type = models.CharField(max_length=20, choices=STORY_TYPE_CHOICES, default="article")
    survey = models.ForeignKey("SurveyHeader", on_delete=models.SET_NULL, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    published_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'survey'
        verbose_name_plural = 'stories'

    def __str__(self):
        return self.title

    def get_story_type_display_label(self):
        return dict(STORY_TYPE_CHOICES).get(self.story_type, self.story_type)


class AbuseEvent(models.Model):
    """Audit log of triggered abuse defenses on the registration endpoint.

    Each defense (captcha, ratelimit, honeypot) writes one row when it
    blocks a request. The Phase 3 anomaly dashboard queries this table.
    The 'email_domain' choice is reserved for the Phase 2 disposable-domain
    blocklist defense; including it here avoids a future migration.

    Intentionally does NOT persist email or attempted username — those have
    GDPR retention concerns. They MAY appear in the operational log line for
    short-lived diagnostic use but are never stored.
    """

    DEFENSE_CHOICES = (
        ('captcha', 'Turnstile CAPTCHA'),
        ('ratelimit', 'Rate Limit'),
        ('honeypot', 'Honeypot'),
        ('email_domain', 'Disposable Email Domain'),
    )

    defense = models.CharField(max_length=20, choices=DEFENSE_CHOICES, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'survey'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.defense} from {self.ip} at {self.created_at}"


class AuditLog(models.Model):
    """Append-only audit log of destructive/lifecycle editor operations.

    References the target survey by stored uuid+name (no FK) so records
    survive a permanent purge; the actor FK uses SET_NULL so records survive
    account deletion. Rows are written via survey.audit.audit() which never
    raises, and are read-only in the admin. See
    openspec/changes/survey-deletion-safety/design.md (D4, D5).
    """

    ACTION_CHOICES = (
        ('survey_trash', 'Survey moved to trash'),
        ('survey_restore', 'Survey restored from trash'),
        ('survey_purge', 'Survey permanently deleted'),
        ('survey_auto_purge', 'Survey auto-purged after retention'),
        ('status_transition', 'Lifecycle status transition'),
        ('clear_test_data', 'Test sessions cleared'),
        ('draft_publish', 'Draft published as new version'),
        ('draft_discard', 'Draft discarded'),
        ('password_set', 'Survey password set'),
        ('password_remove', 'Survey password removed'),
        ('token_regenerate', 'Test token regenerated'),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_entries')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    survey_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    survey_name = models.CharField(max_length=45, blank=True, default='')
    ip = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'survey'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} on '{self.survey_name}' by {self.actor} at {self.created_at}"


class FunnelReport(SurveyHeader):
    """Display-only proxy hosting the staff creator-funnel admin dashboard.

    Has no table of its own; the admin changelist view is fully overridden to render
    aggregates from CreatorFunnelService. See
    openspec/changes/funnel-monitoring/design.md (D1).
    """

    class Meta:
        proxy = True
        app_label = 'survey'
        verbose_name = 'Funnel dashboard'
        verbose_name_plural = 'Funnel dashboard'


class SignupAttribution(models.Model):
    """Acquisition source of a creator, captured at registration.

    First-touch referrer (classified into a bucket) + any UTM params, persisted
    one-to-one with the User. Absence of a row = unknown source (e.g. users who
    registered before this shipped). See funnel-monitoring change (Phase 1).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='signup_attribution',
    )
    raw_referrer = models.CharField(max_length=512, blank=True)
    source_bucket = models.CharField(max_length=20, blank=True)  # direct/google/social/other/...
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return f"{self.user_id}: {self.utm_source or self.source_bucket or 'direct'}"


class UserActivity(models.Model):
    """Last time a user made an authenticated request.

    Unlike `auth_user.last_login` (updated only on explicit authentication) and
    `SurveyHeader.updated_at` (moves only when the parent survey is saved), this
    captures genuine system entry: it is refreshed by `LastActivityMiddleware` on
    any authenticated request, throttled to at most one write per user per
    `LAST_ACTIVITY_THROTTLE_SECONDS`. Absence of a row = no authenticated request
    since this shipped (no backfill). Consumed by the funnel dashboard.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='activity',
    )
    last_activity = models.DateTimeField(db_index=True)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return f"{self.user_id}: {self.last_activity:%Y-%m-%d %H:%M}"


COHORT_SOURCE_CHOICES = (
    ("auto", _("Automatic rule")),
    ("manual", _("Staff assignment")),
)


class CohortDimension(models.Model):
    """An axis along which users are classified, e.g. "Plan" or "Segment".

    Vocabulary, not code: staff add a dimension or a cohort in the admin without a
    migration. A user holds at most one cohort per dimension, so a dimension's
    cohort counts partition the user base -- see the user-cohorts change (D1).
    Analytical labels only: membership grants nothing.
    """

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'survey'
        ordering = ('order', 'name')

    def __str__(self):
        return self.name


class Cohort(models.Model):
    """One value within a dimension, e.g. "Pro" in Plan or "Universities" in Segment."""

    dimension = models.ForeignKey(
        CohortDimension, on_delete=models.CASCADE, related_name='cohorts',
    )
    slug = models.SlugField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=7, blank=True,
        help_text=_('Hex colour used on the funnel dashboard, e.g. #3b82f6.'),
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'survey'
        ordering = ('dimension__order', 'order', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('dimension', 'slug'), name='unique_cohort_slug_per_dimension',
            ),
        ]

    def __str__(self):
        return f"{self.dimension.name}: {self.name}"


class UserCohort(models.Model):
    """Assignment of one cohort to one user, at most one per dimension.

    `dimension` is denormalised from `cohort.dimension` so the one-per-dimension
    rule is expressible as a database constraint; `save()` keeps the two in sync
    rather than trusting callers. `source` records who decided: automatic
    classification never touches a `manual` row (user-cohorts change, D2).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cohorts',
    )
    dimension = models.ForeignKey(
        CohortDimension, on_delete=models.CASCADE, related_name='assignments',
    )
    cohort = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name='assignments',
    )
    source = models.CharField(max_length=10, choices=COHORT_SOURCE_CHOICES, default='manual')
    note = models.CharField(max_length=255, blank=True)
    assigned_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'survey'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'dimension'), name='unique_user_cohort_per_dimension',
            ),
        ]

    def save(self, *args, **kwargs):
        self.dimension = self.cohort.dimension
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'cohort' in update_fields:
            kwargs['update_fields'] = list(update_fields) + ['dimension']
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}: {self.cohort}"


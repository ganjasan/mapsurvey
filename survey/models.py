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

# `published`/`closed` -> `draft` is permitted only while the survey has never
# collected anything; the condition lives in can_transition_to. It is an undo for
# publishing by accident, not a way to edit a survey that has responses — that is
# what draft copies and versioning are for.
VALID_TRANSITIONS = {
    "draft": ["testing", "published"],
    "testing": ["draft", "published"],
    "published": ["closed", "draft"],
    "closed": ["published", "archived", "draft"],
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
    ("ranking", _("Ranking")),
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
    ("stars", _("Stars")),
    ("dropdown", _("Dropdown with search")),
)

# What a star rating looks like when its creator set neither icon nor colour.
# Resolved at render time rather than written into the database, so no existing
# rating question changes until someone opts into the style.
DEFAULT_STAR_ICON = "fas fa-star"
DEFAULT_STAR_COLOR = "#f5b301"

# A star rating that was never given choices still has to render something,
# and "five stars" is what everyone means by a star rating. The steps are
# numbered rather than named: a label per star is meaningless for this style,
# and the number is what an export should show.
DEFAULT_STAR_COUNT = 5

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
        return value if value in ('scale_strip', 'list_pips', 'stars') else 'scale_strip'

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

        if new_status == "draft" and self.status in ("published", "closed"):
            if not self.has_never_collected():
                return False, (
                    "This survey has already collected responses. "
                    "Create a draft copy to edit it instead — that keeps the "
                    "responses collected so far as an archived version."
                )

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
        # Only >1 language warrants asking the respondent to choose one.
        return bool(self.available_languages and len(self.available_languages) > 1)

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
    def has_never_collected(self):
        """True when nothing has ever been recorded against this survey.

        Both halves are needed. Publishing a new version moves the previous
        sessions onto an archived header, so a canonical survey can show zero
        sessions of its own while the survey has collected plenty — checking
        only the session count would read that as untouched.
        """
        if SurveySession.objects.filter(survey=self).exists():
            return False
        return not SurveyHeader.objects.filter(
            canonical_survey=self, is_canonical=False,
        ).exists()

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

    def answer_count(self):
        """Answers that deleting this section would destroy.

        Sub-questions carry the same `survey_section` as their parent — that is
        why `questions()` above has to filter them out — so this one filter
        already covers them, at any nesting depth.
        """
        return Answer.objects.filter(question__survey_section=self).count()

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
    display_style = models.CharField(max_length=20, choices=DISPLAY_STYLE_CHOICES, default="default", help_text=_('Rendering style: rating styles ("default" inherits the survey-wide style) or "dropdown" for choice questions'))

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

    def descendant_question_ids(self):
        """This question's id plus every sub-question beneath it.

        The editor only offers one level of sub-question today, but the model
        allows deeper nesting, so this walks rather than assuming a depth — an
        undercount here would understate what a delete destroys, which is the
        one number this must not get wrong.
        """
        ids = [self.id]
        frontier = [self.id]
        while frontier:
            children = list(
                Question.objects.filter(parent_question_id__in=frontier)
                .values_list('id', flat=True)
            )
            if not children:
                break
            ids.extend(children)
            frontier = children
        return ids

    def answer_count(self):
        """Answers that deleting this question would destroy, sub-questions included."""
        return Answer.objects.filter(question_id__in=self.descendant_question_ids()).count()

    def get_translated_name(self, lang):
        # Unsaved instances (the editor's live-preview drafts) have no
        # translations relation to query.
        if not lang or self.pk is None:
            return self.name
        try:
            translation = self.translations.get(language=lang)
            return translation.name if translation.name else self.name
        except QuestionTranslation.DoesNotExist:
            return self.name

    def get_translated_subtext(self, lang):
        if not lang or self.pk is None:
            return self.subtext
        try:
            translation = self.translations.get(language=lang)
            return translation.subtext if translation.subtext else self.subtext
        except QuestionTranslation.DoesNotExist:
            return self.subtext

    def ranking_items(self, language=None):
        """Items a ranking question asks the respondent to order."""
        return [
            {"code": c["code"], "name": self.get_choice_name(c["code"], language) or str(c["code"])}
            for c in (self.choices or [])
        ]

    def star_choices(self):
        """Choices a star rating lays out, defaulting to five numbered steps.

        Kept out of the database: a question set to stars without choices gets
        1..5 at render time, so the style works the moment it is picked and no
        existing question is rewritten. Names are the numbers themselves, which
        is what a star answer should read as in an export.
        """
        if self.choices:
            return self.choices
        return [{"code": i, "name": str(i)} for i in range(1, DEFAULT_STAR_COUNT + 1)]

    def star_icon(self):
        """Icon a star rating draws, falling back to a solid star."""
        return (self.icon_class or "").strip() or DEFAULT_STAR_ICON

    def star_color(self):
        """Colour a star rating draws in, falling back to gold.

        `color` defaults to #000000 on every question, so black is read as
        "never set" rather than as a deliberate choice — black stars are not
        what an untouched question should render, and back-filling gold onto
        existing questions would be a migration that changes questions nobody
        asked to change. A creator who really wants black can pick #000001.
        """
        value = (self.color or "").strip()
        return value if value and value.lower() != "#000000" else DEFAULT_STAR_COLOR

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


class DomainSegmentRule(models.Model):
    """Maps one organisation's email domain to a segment cohort.

    Lives in the database rather than in code because this repository is public
    and the list of domains is, in effect, our customer roster. Generic rules
    (freemail, `.edu`, `.gov.uk`) stay in `survey/cohorts.py` -- they name nobody.
    See openspec/changes/domain-rules-to-db/design.md (D1).

    Loaded from a gitignored file via `assign_cohorts --rules-csv`, so the
    production rule set is reproducible without being committed.
    """

    domain = models.CharField(max_length=200, unique=True)
    cohort = models.ForeignKey(
        'Cohort', on_delete=models.CASCADE, related_name='domain_rules',
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'survey'
        ordering = ('domain',)

    def save(self, *args, **kwargs):
        self.domain = self.domain.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.domain} -> {self.cohort_id}"


NOTE_KIND_CHOICES = (
    ("research", _("Research")),
    ("email", _("Email")),
    ("call", _("Call")),
    ("signal", _("Signal")),
)


class CreatorProfile(models.Model):
    """What we know about a registered creator, beyond what the product records.

    Staff-only. Deliberately shaped like the Contact/Company columns of a CRM so
    the eventual migration is a file handover -- see the creator-dossiers change
    (D1). Every field is optional; an absent profile means "nothing recorded
    yet", never an error.

    These are personal notes about identifiable people: a GDPR subject access
    request obliges us to hand them over verbatim (`export_creators --username`).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='creator_profile',
    )
    organization = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=100, blank=True)
    linkedin_url = models.URLField(max_length=300, blank=True)
    website = models.URLField(max_length=300, blank=True)
    how_found_us = models.CharField(max_length=255, blank=True)
    summary = models.TextField(
        blank=True, help_text=_('Short markdown summary: who this is, in a few lines.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return f"{self.user_id}: {self.organization or '—'}"


class CreatorNote(models.Model):
    """One dated entry in a creator's timeline: research, an email, a call.

    Append-only by convention: tooling only ever creates notes, so the history of
    a relationship stays a record of what was known when (design D2). Staff may
    still fix a typo by hand. `source_path` records where an imported note came
    from and is what makes re-running the importer safe (D4).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='creator_notes',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authored_creator_notes',
    )
    kind = models.CharField(max_length=10, choices=NOTE_KIND_CHOICES, default='research')
    happened_on = models.DateField()
    body = models.TextField()
    source_path = models.CharField(
        max_length=500, blank=True, db_index=True,
        help_text=_('Repo-relative path this note was imported from, if any.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'survey'
        ordering = ('-happened_on', '-id')
        indexes = [
            models.Index(fields=('user', 'happened_on')),
        ]

    def __str__(self):
        return f"{self.user_id} {self.happened_on:%Y-%m-%d} {self.kind}"


# -- acquisition metrics (top of the creator funnel) ---------------------------

ACQUISITION_SOURCES = (
    ('gsc', 'Google Search Console'),
    ('plausible', 'Plausible'),
)

# Sync state, derived rather than stored: see AcquisitionSyncState.state.
SYNC_NOT_CONFIGURED = 'not_configured'
SYNC_OK = 'ok'
SYNC_FAILING = 'failing'
SYNC_NEVER_RUN = 'never_run'


class AcquisitionDaily(models.Model):
    """One day of metrics from one external analytics provider.

    The funnel dashboard reads these rows instead of calling GSC/Plausible during a
    request (design D1). Metrics that a source does not report stay NULL, so a
    missing metric is distinguishable from a measured zero (D2).

    `segment` slices the day within a source and its meaning is per-source (D3):

    - `gsc`: `''` = the whole property, `marketing` = marketing pages only
      (survey pages excluded -- those are our customers' respondents, not people
      discovering Mapsurvey).
    - `plausible`: `''` = whole site, `landing` = the landing page,
      `src:<channel>` = visitors attributed to that referrer channel.
    """

    SEGMENT_ALL = ''
    SEGMENT_MARKETING = 'marketing'
    SEGMENT_LANDING = 'landing'
    CHANNEL_PREFIX = 'src:'

    source = models.CharField(max_length=20, choices=ACQUISITION_SOURCES)
    date = models.DateField()
    segment = models.CharField(
        max_length=60, blank=True, default='',
        help_text=_('Slice within the source; meaning depends on the source.'),
    )

    # Search Console metrics.
    impressions = models.IntegerField(null=True, blank=True)
    clicks = models.IntegerField(null=True, blank=True)
    ctr = models.FloatField(null=True, blank=True)
    position = models.FloatField(null=True, blank=True)

    # Plausible metrics.
    visitors = models.IntegerField(null=True, blank=True)
    pageviews = models.IntegerField(null=True, blank=True)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'survey'
        constraints = [
            models.UniqueConstraint(
                fields=('source', 'date', 'segment'),
                name='unique_acquisition_daily',
            ),
        ]
        indexes = [
            models.Index(fields=('source', 'date')),
        ]
        ordering = ('-date', 'source', 'segment')

    def __str__(self):
        return f"{self.source} {self.date} {self.segment or 'all'}"

    @property
    def channel(self):
        """Referrer channel for `src:<channel>` rows, else ''."""
        if self.segment.startswith(self.CHANNEL_PREFIX):
            return self.segment[len(self.CHANNEL_PREFIX):]
        return ''


class AcquisitionSyncState(models.Model):
    """Per-source outcome of the last synchronisation attempt.

    Read by the dashboard so a silently stalled cron job is visible next to the
    numbers it feeds (design D6). A source that was never configured, one that is
    configured and succeeding, and one that is configured but failing are three
    different states and must not render alike.
    """

    source = models.CharField(max_length=20, choices=ACQUISITION_SOURCES, unique=True)
    is_configured = models.BooleanField(default=False)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')

    class Meta:
        app_label = 'survey'
        ordering = ('source',)

    def __str__(self):
        return f"{self.source}: {self.state}"

    @property
    def state(self):
        if not self.is_configured:
            return SYNC_NOT_CONFIGURED
        if self.last_error:
            return SYNC_FAILING
        if self.last_success_at is None:
            return SYNC_NEVER_RUN
        return SYNC_OK


class DemoOpen(models.Model):
    """A respondent session started on the demo survey.

    Written only for the survey behind `DEMO_SURVEY_URL`, which is ours -- its
    respondents are prospects evaluating Mapsurvey. The user FK lives here rather
    than on `SurveySession` so that recording it never starts linking our
    customers' respondents to platform accounts (design D4).

    Forward-only from deploy: the full-history *total* of demo opens is derived
    from sessions, only the anonymous/signed-in split comes from these rows.
    """

    session = models.OneToOneField(
        'SurveySession', on_delete=models.CASCADE, related_name='demo_open',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='demo_opens',
        help_text=_('Set when the demo was opened by a signed-in user; NULL = anonymous.'),
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = 'survey'
        ordering = ('-created_at',)

    def __str__(self):
        who = self.user_id or 'anonymous'
        return f"demo open {self.created_at:%Y-%m-%d} by {who}"


PUBLIC_RESULTS_VISIBILITY_CHOICES = (
    ("public", _("Public")),
    ("unlisted", _("Unlisted")),
)

PUBLIC_RESULTS_MODE_CHOICES = (
    ("live", _("Live")),
    ("frozen", _("Frozen")),
)

PUBLIC_RESULTS_BLOCK_TYPE_CHOICES = (
    ("text", _("Text")),
    ("image", _("Image")),
    ("chart", _("Chart")),
    ("map", _("Map")),
)

# Current snapshot serialization format. Bumped when the per-block payload
# shape changes so a stale snapshot can show a "re-freeze needed" notice
# instead of rendering wrong/broken data.
PUBLIC_RESULTS_SNAPSHOT_VERSION = 1


class PublicResultsPage(models.Model):
    """Creator-curated public page of aggregated survey results.

    Bound 1:1 to a SurveyHeader. Renders live aggregates through
    SurveyAnalyticsService (mode='live') or from a stored snapshot
    (mode='frozen'). Served at /r/<slug>/ only when is_published is True.
    """

    survey = models.OneToOneField(
        "SurveyHeader", on_delete=models.CASCADE, related_name="public_results_page"
    )
    slug = models.SlugField(max_length=64, unique=True)
    visibility = models.CharField(
        max_length=10, choices=PUBLIC_RESULTS_VISIBILITY_CHOICES, default="public",
        help_text=_('Public is indexable and listable; unlisted is reachable by direct link only.')
    )
    is_published = models.BooleanField(default=False)
    intro = models.JSONField(
        default=dict, blank=True,
        help_text=_('Multilingual intro: {"title": {"en": ...}, "body": {"en": ...}} or plain strings.')
    )
    mode = models.CharField(max_length=10, choices=PUBLIC_RESULTS_MODE_CHOICES, default="live")
    snapshot = models.JSONField(null=True, blank=True, help_text=_('Frozen per-block payloads.'))
    snapshot_version = models.PositiveIntegerField(null=True, blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    show_response_count = models.BooleanField(default=True)
    show_participate_cta = models.BooleanField(default=True)
    show_on_thanks = models.BooleanField(
        default=True, help_text=_('Show a "See the results" button on the survey\'s thanks page (only while published).')
    )
    feature_in_listing = models.BooleanField(
        default=False, help_text=_('Show a card in the public stories listing (public visibility only).')
    )
    k_anonymity_threshold = models.PositiveIntegerField(
        default=3, help_text=_('Mask buckets with 0 < count < K as "<K". Set to 1 to disable.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'survey'

    def __str__(self):
        return f"Public results: {self.slug}"

    def is_frozen(self):
        return self.mode == "frozen"


class PublicResultsBlock(models.Model):
    """One ordered block on a PublicResultsPage.

    A block is either bound to a question (chart/map) or standalone
    (text/image). Data within the block is live or frozen per the page.
    """

    page = models.ForeignKey(
        PublicResultsPage, on_delete=models.CASCADE, related_name="blocks"
    )
    question = models.ForeignKey(
        "Question", on_delete=models.SET_NULL, null=True, blank=True,
        help_text=_('Bound question for chart/map blocks; null for text/image.')
    )
    block_type = models.CharField(max_length=10, choices=PUBLIC_RESULTS_BLOCK_TYPE_CHOICES)
    viz = models.CharField(
        max_length=20, default="auto",
        help_text=_('Visualization override: auto, bar, pie, donut, table, heatmap, ...')
    )
    custom_title = models.JSONField(
        default=dict, blank=True, help_text=_('Optional multilingual title override.')
    )
    content = models.JSONField(
        default=dict, blank=True,
        help_text=_('Multilingual body for standalone text blocks, or caption for image blocks: {"en": "...", "ru": "..."}.')
    )
    image = models.ImageField(
        upload_to='public_results_blocks/', null=True, blank=True,
        help_text=_('Image for standalone image blocks.')
    )
    geo_label_fields = models.JSONField(
        default=list, blank=True,
        help_text=_('Question codes whose values appear in geo popups. Empty = anonymous geometry only.')
    )
    basemap = models.CharField(
        max_length=20, default='streets', choices=BASEMAP_CHOICES,
        help_text=_('Tile basemap for map blocks (streets/satellite/topo).')
    )
    is_hidden = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'survey'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.block_type} block on {self.page.slug}"



AI_GENERATION_KIND_CHOICES = (
    ('survey_draft', _('Survey draft generation')),
    # AI analytics (#92) and AI response triage (#95) append values here — no
    # schema change needed when they land.
)

AI_GENERATION_OUTCOME_CHOICES = (
    ('pending', _('Pending')),
    ('success', _('Success')),
    ('not_configured', _('Provider not configured')),
    ('provider_error', _('Provider error')),
    ('invalid_draft', _('Invalid draft')),
    ('error', _('Unexpected error')),
)


class AIGenerationEvent(models.Model):
    """One LLM generation attempt — survey drafts today, analytics/triage later.

    Doubles as the async task-state row (`pending` → terminal outcome): the
    create page polls a status endpoint that reads this row, so generation
    state survives worker restarts and is inspectable in the admin. Also the
    substrate for future per-organization quotas (#87 counts rows) and for
    cost tracking (token usage is stored per attempt).

    The brief is creator-authored project description (never respondent data);
    it is kept because reading real briefs against their outcomes is the only
    way to iterate on prompt quality.
    """

    kind = models.CharField(max_length=30, choices=AI_GENERATION_KIND_CHOICES, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_generation_events',
    )
    organization = models.ForeignKey(
        'Organization', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_generation_events',
    )
    created_survey = models.ForeignKey(
        'SurveyHeader', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_generation_events',
    )
    brief = models.JSONField(default=dict, blank=True)
    languages = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=30, blank=True, default='')
    model = models.CharField(max_length=80, blank=True, default='')
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    # Latency accounting, deliberately three fields rather than one redefined.
    # `latency_ms` above keeps meaning the TERMINAL provider call, which is what
    # the rows written before this existed were actually measured as -- widening
    # it in place would have made history say something it never measured.
    # `attempts`/`total_latency_ms` cover the whole set, so a generation that
    # retried stops being indistinguishable from a single slow one. For a
    # single-attempt set, total_latency_ms == latency_ms and attempts == 1.
    #
    # `thinking_tokens` is null when the provider did not report reasoning usage
    # (see client._thinking_tokens) -- never 0, which would be a measurement.
    attempts = models.IntegerField(null=True, blank=True)
    total_latency_ms = models.IntegerField(null=True, blank=True)
    thinking_tokens = models.IntegerField(null=True, blank=True)
    # How much of the draft has actually been written, updated as it streams.
    # The worker cannot talk to the polling request, so the row is the channel —
    # the same reasoning that put last_polled_at and redirected_at here, with
    # the same benefit: a worker restart leaves a visible partial state instead
    # of a silently lost one. Null until the first section closes, because a
    # displayed 0 during the model's opening reasoning reads as a stall.
    sections_drafted = models.IntegerField(null=True, blank=True)
    questions_drafted = models.IntegerField(null=True, blank=True)
    outcome = models.CharField(
        max_length=20, choices=AI_GENERATION_OUTCOME_CHOICES, default='pending',
        db_index=True,
    )
    error_detail = models.TextField(blank=True, default='')
    # Hypothesis telemetry, written server-side (no client JS to lose):
    # - generated_blob: the model output as validated, BEFORE the creator edits
    #   anything. Diffing it against the published survey measures how much
    #   manual repair a draft needed — the honest quality metric.
    # - last_polled_at: the create page polls every 2s while pending, so this
    #   is effectively "when the creator stopped waiting" if they left.
    # - redirected_at: set when the status endpoint issues the HX-Redirect,
    #   i.e. the creator was still on the page when the draft finished.
    generated_blob = models.JSONField(null=True, blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    redirected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = 'survey'
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.kind} {self.outcome} by {self.user_id or 'unknown'} at {self.created_at:%Y-%m-%d %H:%M}"

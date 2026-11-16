"""Reports (change reports-object, #703; epic #712).

A `Report` is a workspace object served at `/r/<slug>/`; a `ReportBlock` names a dataset of the
Data module and, for a block about one question, that question's CODE — never a question row,
because publishing unpublished changes replaces the rows. Today's public results pages are the
first reports (migration `0002`).
"""
import uuid as uuid_module

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

VISIBILITY_CHOICES = (
    ('public', _('Public')),
    ('unlisted', _('Unlisted')),
    ('workspace', _('Workspace only')),
)

MODE_CHOICES = (
    ('live', _('Live')),
    ('frozen', _('Frozen')),
)

BLOCK_TYPE_CHOICES = (
    ('heading', _('Heading')),   # a section title of the story (change reports-story, #704)
    ('text', _('Text')),
    ('image', _('Image')),
    ('numbers', _('Key numbers')),   # a strip of value + label, typed by hand
    ('quotes', _('Quotes')),         # text + source line, typed or pasted by the author
    ('chart', _('Chart')),
    ('map', _('Map')),
    ('objects', _('Objects')),   # per-object aggregates of an Objects-on-the-map question
    ('budget', _('Budget')),     # a budget question's aggregate
)

# Block types that show one question of a dataset.
QUESTION_BLOCK_TYPES = ('chart', 'map', 'objects', 'budget')
# Block types the author writes: nothing in them is computed.
STORY_BLOCK_TYPES = ('heading', 'text', 'image', 'numbers', 'quotes')

WIDTH_CHOICES = (('full', _('Full width')), ('half', _('Half width')))
MAX_ITEMS = 12          # values in a Key numbers block, quotes in a Quotes block

# Current snapshot serialization format. Bumped when the per-block payload shape changes so a stale
# snapshot shows a "re-freeze needed" notice instead of wrong data.
SNAPSHOT_VERSION = 3   # 2: spraycan density grid; 3: every map block is a grid (data-aggregate)

DEFAULT_K = 3


class Report(models.Model):
    """A creator-curated page of aggregated results, live or frozen, at /r/<slug>/ when published.

    `survey` is the report's home survey (the one whose Public results tab opens it), not an
    owner of its data: blocks name their own datasets and may read several surveys.
    """

    uuid = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='reports')
    survey = models.ForeignKey('survey.SurveyHeader', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='reports')
    slug = models.SlugField(max_length=64, unique=True)
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default='public',
        help_text=_('Public is indexable and listable; unlisted is reachable by direct link only; '
                    'workspace only opens for signed-in members.'))
    is_published = models.BooleanField(default=False)
    intro = models.JSONField(
        default=dict, blank=True,
        help_text=_('Multilingual intro: {"title": {"en": ...}, "body": {"en": ...}} or plain strings.'))
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='live')
    snapshot = models.JSONField(null=True, blank=True, help_text=_('Frozen per-block payloads.'))
    snapshot_version = models.PositiveIntegerField(null=True, blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    show_response_count = models.BooleanField(default=True)
    show_participate_cta = models.BooleanField(default=True)
    show_on_thanks = models.BooleanField(
        default=True,
        help_text=_('Show a "See the results" button on the survey\'s thanks page (only while published).'))
    feature_in_listing = models.BooleanField(
        default=False, help_text=_('Show a card in the public stories listing (public visibility only).'))
    k_anonymity_threshold = models.PositiveIntegerField(
        default=DEFAULT_K, help_text=_('Mask buckets with 0 < count < K as "<K". Set to 1 to disable.'))
    scaffolded_at = models.DateTimeField(
        null=True, blank=True,
        help_text=_('When default blocks were auto-drafted. Set once; blocks the creator deletes are never re-created.'))
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return f'Report: {self.slug}'

    def save(self, *args, **kwargs):
        if self.organization_id is None and self.survey_id is not None:
            self.organization_id = self.survey.organization_id
        super().save(*args, **kwargs)

    def is_frozen(self):
        return self.mode == 'frozen'

    @property
    def title(self):
        """What lists call the report: its intro title, else its survey's name, else the slug."""
        value = (self.intro or {}).get('title')
        if isinstance(value, dict):
            value = value.get('en') or next(iter(value.values()), '')
        return value or (self.survey.name if self.survey_id else '') or self.slug


class ReportBlockManager(models.Manager):
    def create(self, **kwargs):
        """`question=<Question>` names the block's source for you: the dataset that question's
        answers live in and its code."""
        question = kwargs.pop('question', None)
        if question is not None:
            from reports.sources import dataset_for
            kwargs.setdefault('dataset', dataset_for(question))
            kwargs.setdefault('question_code', question.code)
        return super().create(**kwargs)


class ReportBlock(models.Model):
    """One ordered block of a report.

    A question block (chart / map / objects / budget) names `dataset` — a survey's `answers`
    dataset for a map, its `responses` dataset otherwise — and `question_code`. Text and image
    blocks name nothing. Data inside the block is live or frozen per the report.
    """

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='blocks')
    block_type = models.CharField(max_length=10, choices=BLOCK_TYPE_CHOICES)
    # SET_NULL: `data.datasets.sync` drops a collected dataset whose question is gone; the block
    # then renders nothing, as a block of a deleted question always did.
    dataset = models.ForeignKey('data.Dataset', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='report_blocks')
    # A saved view of the dataset instead of all of it; a view in use cannot be deleted.
    view = models.ForeignKey('data.DatasetView', null=True, blank=True, on_delete=models.RESTRICT,
                             related_name='report_blocks')
    question_code = models.CharField(max_length=50, blank=True, default='')
    viz = models.CharField(
        max_length=20, default='auto',
        help_text=_('Visualization override: auto, bar, pie, donut, table, heatmap, ...'))
    custom_title = models.JSONField(default=dict, blank=True, help_text=_('Optional multilingual title override.'))
    content = models.JSONField(
        default=dict, blank=True,
        help_text=_('Multilingual body for standalone text blocks, or caption for image blocks: {"en": "...", "ru": "..."}.'))
    image = models.ImageField(upload_to='public_results_blocks/', null=True, blank=True,
                              help_text=_('Image for standalone image blocks.'))
    geo_label_fields = models.JSONField(
        default=list, blank=True,
        help_text=_('Question codes whose values appear in geo popups. Empty = anonymous geometry only.'))
    basemap = models.CharField(
        max_length=50, default='streets',
        help_text=_('Tile basemap for map blocks: a preset key or "style:<uuid>" of a workspace map style.'))
    # What a story block holds beyond its text (change reports-story):
    # numbers → {'items': [{'value', 'label'}]}; quotes → {'items': [{'text', 'source'}]}.
    # `reports.story.clean_config` is the one writer.
    config = models.JSONField(default=dict, blank=True)
    # Two consecutive half-width blocks sit side by side on a wide screen.
    width = models.CharField(max_length=4, choices=WIDTH_CHOICES, default='full')
    is_hidden = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    objects = ReportBlockManager()

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.block_type} block on {self.report.slug}'

    @cached_property
    def question(self):
        """The question this block shows, as it stands in the dataset's survey today (or None)."""
        from reports.sources import question_for
        return question_for(self)

    @property
    def question_id(self):
        q = self.question
        return q.pk if q is not None else None

    @property
    def source_survey(self):
        """The canonical survey whose answers the block reads (or None)."""
        return self.dataset.survey if self.dataset_id and self.dataset.survey_id else None

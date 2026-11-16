"""The dataset registry (change data-catalogue, #667; ADR-001 §4).

A `Dataset` is a registry row over data that lives elsewhere — a reference layer, a shared map,
a survey's answers to one geo question, a survey's respondent rows. Nothing moves into it; it
gives every place dataset of a workspace one identity that the catalogue, the dataset page,
"From Data" links, versions, views, tags and the API hang off. Rows are created and dropped by
`data.datasets.sync(org)`.
"""
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Dataset(models.Model):
    KIND_LAYER = 'layer'            # a creator's reference layer: uploaded or drawn objects
    KIND_SHARED_MAP = 'shared_map'  # a layer materialised from respondents' answers
    KIND_ANSWERS = 'answers'        # a survey's answers to one top-level geo question (by code)
    KIND_RESPONSES = 'responses'    # a survey's respondent rows
    KIND_CHOICES = [
        (KIND_LAYER, _('Layer')),
        (KIND_SHARED_MAP, _('Shared map')),
        (KIND_ANSWERS, _('Answers')),
        (KIND_RESPONSES, _('Responses')),
    ]
    LAYER_KINDS = (KIND_LAYER, KIND_SHARED_MAP)
    COLLECTED_KINDS = (KIND_ANSWERS, KIND_RESPONSES)

    PRIVACY_PUBLIC = 'public'
    PRIVACY_AGGREGATED = 'aggregated'
    PRIVACY_PRIVATE = 'private'
    PRIVACY_CHOICES = [
        (PRIVACY_PUBLIC, _('Public')),
        (PRIVACY_AGGREGATED, _('Aggregated')),
        (PRIVACY_PRIVATE, _('Private')),
    ]

    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='datasets')
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    layer = models.ForeignKey('survey.SurveyMapLayer', null=True, blank=True, on_delete=models.CASCADE,
                              related_name='datasets')
    survey = models.ForeignKey('survey.SurveyHeader', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='datasets',
                               help_text=_('The canonical survey: collected kinds span its versions.'))
    question_code = models.CharField(max_length=50, blank=True, default='')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    privacy_class = models.CharField(max_length=12, choices=PRIVACY_CHOICES, default=PRIVACY_PRIVATE)
    # Closed list (owner 2026-11-14); `data.fields.LICENCES` names them.
    LICENCE_CHOICES = [
        ('ogl-uk-3.0', 'Open Government Licence v3.0'),
        ('cc-by-4.0', 'CC BY 4.0'),
        ('cc0-1.0', 'CC0 1.0'),
        ('dl-de-by-2.0', 'Datenlizenz Deutschland – Namensnennung 2.0'),
    ]
    # The DCAT-AP data themes (EU vocabulary) — what an open-data feed (#675) publishes.
    THEME_CHOICES = [
        ('AGRI', _('Agriculture, fisheries, forestry and food')),
        ('ECON', _('Economy and finance')),
        ('EDUC', _('Education, culture and sport')),
        ('ENER', _('Energy')),
        ('ENVI', _('Environment')),
        ('GOVE', _('Government and public sector')),
        ('HEAL', _('Health')),
        ('INTR', _('International issues')),
        ('JUST', _('Justice, legal system and public safety')),
        ('REGI', _('Regions and cities')),
        ('SOCI', _('Population and society')),
        ('TECH', _('Science and technology')),
        ('TRAN', _('Transport')),
    ]
    FREQUENCY_CHOICES = [
        ('as_needed', _('As needed')),
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('yearly', _('Yearly')),
        ('never', _('Never updated')),
    ]
    licence = models.CharField(max_length=32, blank=True, default='', choices=LICENCE_CHOICES)
    theme = models.CharField(max_length=8, blank=True, default='', choices=THEME_CHOICES)
    maintainer = models.CharField(max_length=200, blank=True, default='',
                                  help_text=_('The team or role that keeps the dataset current.'))
    update_frequency = models.CharField(max_length=12, blank=True, default='', choices=FREQUENCY_CHOICES)
    # The field dictionary: [{'name', 'label', 'type', 'description', 'private'}] (data-upload
    # writes it, data-metadata edits it). A private field never leaves the dataset's own editor —
    # `data.fields` is the rule every output goes through.
    fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(fields=['layer'], condition=Q(layer__isnull=False),
                                    name='data_dataset_one_per_layer'),
            models.UniqueConstraint(fields=['survey', 'kind', 'question_code'],
                                    condition=Q(kind__in=('answers', 'responses')),
                                    name='data_dataset_one_per_collected_source'),
            models.CheckConstraint(
                condition=(Q(kind__in=('layer', 'shared_map'), layer__isnull=False)
                           | Q(kind__in=('answers', 'responses'), survey__isnull=False)),
                name='data_dataset_source_matches_kind'),
        ]

    def __str__(self):
        return f'{self.name} ({self.kind})'


class DatasetView(models.Model):
    """A saved, named filter, field set and colour over a dataset (change data-views, #672). Its id is
    stable across versions: it names fields, never objects. `kind` follows the dataset's privacy:
    `objects` for a layer, `grid` (counts of distinct respondents, K-masked) for collected answers."""
    KIND_OBJECTS = 'objects'
    KIND_GRID = 'grid'
    # Analysis kinds (change data-analysis-views, #692): computed by `data.analysis`, always
    # masked. `responses` is a saved filter of the Responses table (`data.responses_views`).
    KIND_ENGAGEMENT = 'engagement'
    KIND_CROSSTAB = 'crosstab'
    KIND_COVERAGE = 'coverage'
    KIND_DENSITY = 'density'
    KIND_RESPONSES = 'responses'
    KIND_CHOICES = [
        (KIND_OBJECTS, _('Objects')),
        (KIND_GRID, _('Grid of counts')),
        (KIND_COVERAGE, _('Coverage')),
        (KIND_DENSITY, _('Density')),
        (KIND_ENGAGEMENT, _('Engagement')),
        (KIND_CROSSTAB, _('Cross-tab')),
        (KIND_RESPONSES, _('Responses filter')),
    ]
    CELL_KINDS = (KIND_GRID, KIND_COVERAGE, KIND_DENSITY)      # a FeatureCollection of cells
    TABLE_KINDS = (KIND_ENGAGEMENT, KIND_CROSSTAB)             # a JSON result

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='views')
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=KIND_OBJECTS)
    # What the kind needs: a cross-tab's {'rows': code, 'columns': code}; a Responses filter's
    # table state. Question CODES, never row ids.
    config = models.JSONField(default=dict, blank=True)
    # [{'field', 'op' (eq | in | gt | lt), 'value' (str) | 'values' ([str])}], all must hold.
    conditions = models.JSONField(default=list, blank=True)
    # Public field names the view keeps ([] = every public field).
    fields = models.JSONField(default=list, blank=True)
    color = models.CharField(max_length=7, blank=True, default='')
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class DatasetLink(models.Model):
    """A place that shows a dataset without a copy (change data-links, #670): a survey's reference
    layers (the CANONICAL survey, like layer ownership) or a Site map block. Every link is a
    "used by" record; `data.links` writes and reads them."""
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='links')
    survey = models.ForeignKey('survey.SurveyHeader', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='dataset_links')
    site_block = models.ForeignKey('survey.SiteBlock', null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='dataset_links')
    # A view of the dataset instead of all of it (change data-views); null = the whole dataset.
    view = models.ForeignKey(DatasetView, null=True, blank=True, on_delete=models.RESTRICT, related_name='links')
    # The public fields the respondent's object card shows for this link ([] = all of them).
    fields = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(fields=['dataset', 'survey'], condition=Q(survey__isnull=False),
                                    name='data_link_one_per_survey'),
            models.UniqueConstraint(fields=['site_block'], condition=Q(site_block__isnull=False),
                                    name='data_link_one_per_site_block'),
            models.CheckConstraint(
                condition=(Q(survey__isnull=False, site_block__isnull=True)
                           | Q(survey__isnull=True, site_block__isnull=False)),
                name='data_link_one_place'),
        ]


def data_import_key(instance, filename):
    """data_imports/<uuid4><ext> on the PRIVATE tier: a random key, never the creator's
    filename, deleted when the job finishes."""
    import os
    import uuid
    ext = os.path.splitext(filename or '')[1].lower()[:10]
    return f'data_imports/{uuid.uuid4().hex}{ext}'


def _private_storage():
    from survey.models import _private_media_storage
    return _private_media_storage()


class DataImportJob(models.Model):
    """A file being turned into a workspace dataset (change data-upload, #668). The upload view
    stores the file and enqueues `data.tasks.run_data_import`; the catalogue shows the card."""
    # A NEW VERSION of a dataset (change data-versions) is a job with `target`: it stops at
    # `preview` with the diff in `report`, keeping the file, until the creator applies it.
    STATUS_CHOICES = [('queued', 'queued'), ('running', 'running'), ('preview', 'preview'),
                      ('applying', 'applying'), ('done', 'done'), ('failed', 'failed')]

    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='data_imports')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='data_imports')
    file = models.FileField(upload_to=data_import_key, storage=_private_storage, max_length=500, blank=True)
    original_name = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued', db_index=True)
    dataset = models.ForeignKey(Dataset, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    target = models.ForeignKey(Dataset, on_delete=models.CASCADE, null=True, blank=True,
                               related_name='version_jobs', help_text='The dataset a new version is for.')
    note = models.CharField(max_length=300, blank=True, default='')
    report = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class DatasetVersion(models.Model):
    """One applied version of a layer dataset (change data-versions, #671): the upload is number 1,
    each "Upload new version" adds the next with its note and counts."""
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='versions')
    number = models.PositiveIntegerField()
    note = models.CharField(max_length=300, blank=True, default='')
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    added = models.PositiveIntegerField(default=0)
    changed = models.PositiveIntegerField(default=0)
    removed = models.PositiveIntegerField(default=0)
    unchanged = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-number']
        constraints = [models.UniqueConstraint(fields=['dataset', 'number'], name='data_version_number_unique')]


class Tag(models.Model):
    """A free workspace tag (change data-tags, #673): how an engagement or programme is grouped
    ("Riverside plan 2027") — the platform has no project entity. One table; each module that takes
    tags adds a relation here. `data.tags.set_tags` is the one writer."""
    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=40)
    slug = models.SlugField(max_length=50, allow_unicode=True)
    datasets = models.ManyToManyField(Dataset, related_name='tags', blank=True)
    # The CANONICAL survey; drafts and versions answer with it.
    surveys = models.ManyToManyField('survey.SurveyHeader', related_name='tags', blank=True)
    # Reports (change reports-usage-api, #710): a report sits beside its surveys and datasets.
    reports = models.ManyToManyField('reports.Report', related_name='tags', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(fields=['organization', 'slug'], name='data_tag_unique_per_workspace')]

    def __str__(self):
        return self.name

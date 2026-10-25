"""Request and response bodies of REST API v1.

Every input schema is an ALLOW-LIST (`extra='forbid'`): a field it does not
name -- `organization`, `status`, `owner`, `created_by`, `geojson`,
`geojson_gz`, ids, timestamps -- is a `422 validation` naming it, never
silently applied or dropped. Output may grow new fields; input never accepts
one it does not list. Rich text is plain `str` here: the service runs it
through `coerce_creator_html`, never the schema.
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional, Union
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field, field_validator

from survey.models import INPUT_TYPE_CHOICES
from survey.redirects import NO_REDIRECT, is_valid_redirect

InputType = Literal[tuple(value for value, _label in INPUT_TYPE_CHOICES)]


class In(Schema):
    model_config = ConfigDict(extra='forbid')


# ─── Shared pieces ───────────────────────────────────────────────────────────

class VisibilityRule(In):
    """Show the item only when an EARLIER choice question was answered with
    one of `choice_codes`, or (`answered: true`) answered at all."""
    question_code: str
    choice_codes: Optional[List[int]] = None
    answered: Optional[bool] = None


class MapStart(In):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zoom: int = Field(ge=0, le=22)


class Page(Schema):
    next_cursor: Optional[str] = None


# ─── Account ─────────────────────────────────────────────────────────────────

class MeUser(Schema):
    id: int
    username: str
    email: str


class MeWorkspace(Schema):
    id: int
    slug: str
    name: str
    role: str
    plan: str
    api: bool = Field(description='Whether the workspace\'s plan includes the API.')


class MeToken(Schema):
    kind: str
    scopes: List[str]
    audiences: List[str]
    organization: Optional[str] = Field(None, description='The workspace the token is bound to, if any.')
    expires: str
    label: str


class MeOut(Schema):
    user: MeUser
    workspaces: List[MeWorkspace]
    token: MeToken


# ─── Surveys ─────────────────────────────────────────────────────────────────

class SurveyOut(Schema):
    uuid: UUID
    name: str
    status: str
    workspace: Optional[str]
    languages: List[str]
    redirect_url: str
    visibility: str
    version: int
    is_unpublished_changes: bool
    live_survey: Optional[UUID] = Field(None, description='For unpublished changes: the live survey they replace.')
    unpublished_changes: Optional[UUID] = Field(None, description='The uuid of this survey\'s unpublished changes, if any.')
    review: Optional[Literal['pending']] = Field(None, description='"pending" while content screening holds the survey.')
    url: str
    created_at: datetime
    updated_at: datetime


class SurveyDetailOut(SurveyOut):
    thanks_html: Dict[str, str]
    basemaps: List[str]
    default_basemap: str
    show_branding: bool
    map_start: Optional[MapStart]
    use_geolocation: bool
    sections: List[int]


class SurveyList(Page):
    items: List[SurveyOut]
    hidden_by_plan: int = Field(0, description='Workspaces of yours whose surveys are hidden: they are on the Free plan.')


class SurveyCreateIn(In):
    name: str = Field(min_length=1, max_length=45)
    workspace: Optional[str] = Field(None, description='Workspace slug; optional when the token is bound to one or you belong to one.')
    language: str = Field('en', min_length=2, max_length=10)
    map_start: Optional[MapStart] = None


def _strict_redirect(value):
    if value is None or value == NO_REDIRECT:
        return value
    if value != value.strip() or not is_valid_redirect(value):
        raise ValueError('Use "#" for the built-in thanks page or a full http(s) address.')
    return value


class SurveyPatchIn(In):
    name: Optional[str] = Field(None, min_length=1, max_length=45)
    redirect_url: Optional[str] = Field(None, description='"#" for the built-in thanks page, or an absolute http(s) URL.')
    languages: Optional[List[str]] = Field(None, min_length=1)
    visibility: Optional[Literal['public', 'private', 'demo']] = None
    basemaps: Optional[List[str]] = None
    default_basemap: Optional[str] = None
    show_branding: Optional[bool] = None
    thanks_html: Optional[Dict[str, str]] = Field(None, description='Thanks page per language; creator HTML, sanitised on save.')
    map_start: Optional[MapStart] = None
    use_geolocation: Optional[bool] = None

    _redirect = field_validator('redirect_url')(_strict_redirect)


class PublishIn(In):
    acknowledge_translation_gaps: bool = False
    clear_test_data: bool = False


class DraftPublishIn(In):
    acknowledge_translation_gaps: bool = False
    force: bool = Field(False, description='Publish even when the changes conflict with collected answers.')


# ─── Sections ────────────────────────────────────────────────────────────────

class SectionTranslation(In):
    title: Optional[str] = None
    subheading: Optional[str] = None
    next_label: Optional[str] = None


class SectionOut(Schema):
    id: int
    code: str
    name: str
    title: Optional[str]
    subheading: Optional[str]
    layout: str
    next_label: Optional[str]
    position: int
    visibility_rule: Optional[dict]
    map_start: Optional[MapStart]
    use_geolocation: bool
    translations: Dict[str, SectionTranslation]
    questions: List[int]


class SectionIn(In):
    title: Optional[str] = Field(None, max_length=256)
    subheading: Optional[str] = None
    code: Optional[str] = Field(None, max_length=8)
    layout: Optional[Literal['map', 'form']] = None
    next_label: Optional[str] = Field(None, max_length=30)
    visibility_rule: Optional[VisibilityRule] = None
    translations: Optional[Dict[str, SectionTranslation]] = None
    map_start: Optional[MapStart] = None
    use_geolocation: Optional[bool] = None


class SectionOrderIn(In):
    section_ids: List[int]


# ─── Questions ───────────────────────────────────────────────────────────────

class ChoiceIn(In):
    code: int
    name: Union[str, Dict[str, str]]
    other: Optional[bool] = None
    icon: Optional[str] = None
    group: Optional[str] = None
    color: Optional[str] = None


class ValidationSettingsIn(In):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    outlier_sigma: Optional[float] = None
    min_length: Optional[int] = None
    area_outlier_factor: Optional[float] = None
    max_dots: Optional[int] = None
    max_file_mb: Optional[int] = None
    max_files: Optional[int] = None
    min_features: Optional[int] = None
    max_features: Optional[int] = None


class QuestionTranslation(In):
    name: Optional[str] = None
    subtext: Optional[str] = None


class QuestionOut(Schema):
    id: int
    code: Optional[str]
    section_id: int
    parent_id: Optional[int]
    group_id: Optional[int]
    order: int
    name: str
    subtext: Optional[str]
    input_type: str
    required: bool
    choices: Optional[list]
    validation_settings: dict
    color: Optional[str]
    icon_class: Optional[str]
    display_style: Optional[str]
    visibility_rule: Optional[dict]
    layer_id: Optional[int]
    min_objects: Optional[int]
    share_with_respondents: bool
    translations: Dict[str, QuestionTranslation]
    subquestions: List[int]


class QuestionIn(In):
    name: Optional[str] = Field(None, max_length=512)
    subtext: Optional[str] = None
    input_type: Optional[InputType] = None
    required: Optional[bool] = None
    choices: Optional[List[ChoiceIn]] = None
    validation_settings: Optional[ValidationSettingsIn] = None
    color: Optional[str] = None
    icon_class: Optional[str] = None
    display_style: Optional[str] = None
    visibility_rule: Optional[VisibilityRule] = None
    layer_id: Optional[int] = None
    layer_from_answers: Optional[str] = Field(
        None, max_length=50,
        description='For an "Objects on the map" question: the code of a map question whose answers become a '
                    'shared map (created on first use). Use instead of `layer_id`.')
    min_objects: Optional[int] = Field(None, ge=0)
    share_with_respondents: Optional[bool] = None
    translations: Optional[Dict[str, QuestionTranslation]] = None


class QuestionCreateIn(QuestionIn):
    input_type: InputType


class QuestionOrderItem(In):
    q: Optional[int] = None
    g: Optional[int] = None


class QuestionOrderIn(In):
    parent_id: Optional[int] = Field(None, description='Order a pop-up\'s sub-questions instead of the section\'s top level.')
    items: List[Union[int, Dict[str, Union[int, List[int]]]]] = Field(
        description='Question ids in order; a group is {"g": <id>, "q": [<ids>]}.')


class ChoicesIn(In):
    choices: List[ChoiceIn]


class DeleteIn(In):
    acknowledge_answer_loss: bool = False


# ─── Layers, import, responses ───────────────────────────────────────────────

class LayerOut(Schema):
    id: int
    name: str
    source: str
    color: Optional[str]
    position: int
    feature_count: Optional[int] = None
    property_names: List[str]
    geojson_url: str


class ImportJobOut(Schema):
    id: int
    status: str
    original_name: str
    survey: Optional[UUID]
    warnings: List[str]
    error: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]


class ResponseOut(Schema):
    id: int
    number: Optional[int] = Field(None, description='The "#N" the Responses page shows; empty sessions have none.')
    survey: UUID
    started_at: Optional[datetime]
    language: Optional[str]
    validation_status: str
    answers: List[dict]


class ResponseList(Page):
    items: List[ResponseOut]


# ─── Responses for agents (change api-v2-responses) ──────────────────────────

class ExportLinkIn(In):
    format: Literal['zip', 'xlsx', 'csv', 'gpkg', 'shp', 'kml'] = 'xlsx'
    version: Optional[str] = Field(None, description='A version number, or omit for every version.')
    include_all: bool = Field(False, description='Also deleted and rejected responses.')
    completed_only: bool = Field(False, description='Only responses that reached the last section.')
    files: bool = Field(False, description='Add uploaded files (turns a single-file format into a ZIP).')


class ExportLinkOut(Schema):
    url: str = Field(description='Open within 15 minutes; it checks your access again.')
    expires_at: datetime


class ModerateIn(In):
    validation_status: Literal['approved', 'not_approved', 'on_hold', '']

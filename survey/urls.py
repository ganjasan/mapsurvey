from django.urls import path

from . import views
from . import editor_views
from . import org_views

urlpatterns = [
    path('', views.index, name='index'),
    path('editor/', views.editor, name='editor'),
    path('editor/export/<uuid:survey_uuid>/', views.export_survey, name='export_survey'),
    path('editor/import/', views.import_survey, name='import_survey'),
    path('editor/delete/<uuid:survey_uuid>/', views.delete_survey, name='delete_survey'),

    # Organization management
    path('org/new/', org_views.org_create, name='org_create'),
    path('org/switch/', org_views.switch_org, name='org_switch'),
    path('org/<slug:slug>/settings/', org_views.org_settings, name='org_settings'),
    path('org/<slug:slug>/members/', org_views.org_members, name='org_members'),
    path('org/<slug:slug>/members/<int:user_id>/role/', org_views.org_change_role, name='org_change_role'),
    path('org/<slug:slug>/members/<int:user_id>/remove/', org_views.org_remove_member, name='org_remove_member'),
    path('org/<slug:slug>/invite/', org_views.org_send_invitation, name='org_send_invitation'),
    path('invitations/<uuid:token>/accept/', org_views.accept_invitation, name='accept_invitation'),

    # WYSIWYG survey editor
    path('editor/surveys/new/', editor_views.editor_survey_create, name='editor_survey_create'),
    path('editor/surveys/<uuid:survey_uuid>/', editor_views.editor_survey_detail, name='editor_survey_detail'),
    path('editor/surveys/<uuid:survey_uuid>/settings/', editor_views.editor_survey_settings, name='editor_survey_settings'),
    path('editor/surveys/<uuid:survey_uuid>/sections/new/', editor_views.editor_section_create, name='editor_section_create'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/', editor_views.editor_section_detail, name='editor_section_detail'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/delete/', editor_views.editor_section_delete, name='editor_section_delete'),
    path('editor/surveys/<uuid:survey_uuid>/sections/reorder/', editor_views.editor_sections_reorder, name='editor_sections_reorder'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/questions/new/', editor_views.editor_question_create, name='editor_question_create'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/edit/', editor_views.editor_question_edit, name='editor_question_edit'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/preview/', editor_views.editor_question_preview, name='editor_question_preview'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/delete/', editor_views.editor_question_delete, name='editor_question_delete'),
    path('editor/surveys/<uuid:survey_uuid>/questions/reorder/', editor_views.editor_questions_reorder, name='editor_questions_reorder'),
    path('editor/surveys/<uuid:survey_uuid>/questions/<int:parent_id>/subquestions/new/', editor_views.editor_subquestion_create, name='editor_subquestion_create'),
    path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/map/', editor_views.editor_section_map_picker, name='editor_section_map_picker'),
    path('editor/surveys/<uuid:survey_uuid>/preview/<str:section_name>/', editor_views.editor_section_preview, name='editor_section_preview'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/', editor_views.editor_survey_collaborators, name='editor_survey_collaborators'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/add/', editor_views.editor_collaborator_add, name='editor_collaborator_add'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/<int:collaborator_id>/role/', editor_views.editor_collaborator_change_role, name='editor_collaborator_change_role'),
    path('editor/surveys/<uuid:survey_uuid>/collaborators/<int:collaborator_id>/remove/', editor_views.editor_collaborator_remove, name='editor_collaborator_remove'),

    path('surveys/', views.survey_list, name='survey_list'),
    path('surveys/<str:survey_slug>/', views.survey_header, name='survey'),
    path('surveys/<str:survey_slug>/language/', views.survey_language_select, name='survey_language_select'),
    path('surveys/<str:survey_slug>/thanks/', views.survey_thanks, name='survey_thanks'),
    path('surveys/<str:survey_slug>/<str:section_name>/', views.survey_section, name='section'),
    path('surveys/<str:survey_slug>/download', views.download_data, name='download_data'),
    path('stories/<slug:slug>/', views.story_detail, name='story_detail'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
]

from django.urls import path

from . import views
from . import editor_views

urlpatterns = [
    path('', views.index, name='index'),
    path('editor/', views.editor, name='editor'),
    path('editor/export/<uuid:survey_uuid>/', views.export_survey, name='export_survey'),
    path('editor/import/', views.import_survey, name='import_survey'),
    path('editor/delete/<uuid:survey_uuid>/', views.delete_survey, name='delete_survey'),

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

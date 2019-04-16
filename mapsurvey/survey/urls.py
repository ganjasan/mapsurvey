from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('surveys/', views.survey_list, name='survey_list'),
    path('surveys/<str:survey_name>/', views.survey_header, name='survey'),
    path('surveys/<str:survey_name>/<str:section_name>/', views.survey_section, name='section'),
    #path('surveys/<str:survey_name>/<str:question_code>/', views.EditAnswerForm.as_view(), name='question'),
]
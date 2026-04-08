from django.urls import path

from . import views

app_name = 'newsletter'

urlpatterns = [
    path('unsubscribe/<uuid:token>/', views.unsubscribe_confirm, name='unsubscribe'),
    path('unsubscribe/<uuid:token>/one-click/', views.unsubscribe_one_click, name='unsubscribe_one_click'),
    path('track/<int:campaign_id>/<int:user_id>/open.gif', views.track_open, name='track_open'),
]

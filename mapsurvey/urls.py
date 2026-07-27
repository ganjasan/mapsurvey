"""mapsurvey URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from django.views.generic import TemplateView

from survey.views import (
    AbuseProtectedRegistrationView,
    DirectActivationView,
    ResendActivationView,
)


urlpatterns = [
 	path('', include('survey.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('accounts/register/', AbuseProtectedRegistrationView.as_view(), name='django_registration_register'),
    # Resend routes must precede the activation include below, which owns the
    # rest of /accounts/activate/.
    path(
        'accounts/activate/resend/',
        ResendActivationView.as_view(),
        name='django_registration_resend_activation',
    ),
    path(
        'accounts/activate/resend/done/',
        TemplateView.as_view(
            template_name='django_registration/resend_activation_done.html'
        ),
        name='django_registration_resend_activation_done',
    ),
    path('accounts/activate/', DirectActivationView.as_view(), name='django_registration_activate'),
    path('accounts/', include('django_registration.backends.activation.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('nl/', include('newsletter.urls', namespace='newsletter')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# Serve media from local disk (in production whitenoise handles only static files)
if not getattr(settings, 'USE_S3', False):
    from django.urls import re_path
    from django.views.static import serve
    urlpatterns += [
        re_path(r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'), serve, {'document_root': settings.MEDIA_ROOT}),
    ]

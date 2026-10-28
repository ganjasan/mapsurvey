from django.urls import path, re_path

from . import views

# Organisation-scoped routes follow survey/urls.py's slug pattern so an
# organisation's settings, members and billing share one address family.
ORG = r'^org/(?P<slug>[-.\w]+)/'

urlpatterns = [
    path('billing/ipn/', views.ipn, name='billing_ipn'),
    path('billing/return/', views.checkout_return, name='billing_return'),
    path('billing/return/status/', views.checkout_status, name='billing_return_status'),
    path('billing/try-pro/', views.try_pro, name='billing_try_pro'),
    re_path(ORG + r'billing/$', views.org_billing, name='org_billing'),
    re_path(ORG + r'billing/checkout/$', views.org_checkout, name='org_checkout'),
    re_path(ORG + r'billing/trial/$', views.org_trial_claim, name='org_billing_trial'),
    re_path(ORG + r'billing/cancel/$', views.org_cancel, name='org_billing_cancel'),
    re_path(ORG + r'billing/resubscribe/$', views.org_resubscribe, name='org_billing_resubscribe'),
    re_path(ORG + r'billing/switch/$', views.org_switch_period, name='org_billing_switch'),
    re_path(ORG + r'billing/login-link/$', views.org_login_link, name='org_billing_login_link'),
    re_path(ORG + r'help/$', views.org_help, name='org_help'),
    path('billing/admin/links/<int:org_id>/', views.admin_payment_links, name='billing_admin_payment_links'),
]

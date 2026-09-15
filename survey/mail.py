"""Transactional mail helpers shared by every sender that renders a template pair.

Comment notifications use them from a Celery task today; the invitation and
activation mails are the intended next callers (they still send synchronously
from their views). Nothing here knows what a comment is.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def absolute_url(path):
    """`settings.SITE_URL` + path — for links built where there is no request."""
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not path.startswith('/'):
        path = '/' + path
    return base + path


def send_templated_mail(template_prefix, to, subject, context, fail_silently=True):
    """Render `<prefix>.txt` and `<prefix>.html` and send both parts to one address."""
    text_body = render_to_string(f'{template_prefix}.txt', context)
    html_body = render_to_string(f'{template_prefix}.html', context)
    return send_mail(
        subject=subject,
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        html_message=html_body,
        fail_silently=fail_silently,
    )

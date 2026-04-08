import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def render_campaign_email(campaign, user, preference, site_url=None):
    """Build an EmailMultiAlternatives for one recipient."""
    if site_url is None:
        site_url = settings.NEWSLETTER_SITE_URL

    unsubscribe_url = f'{site_url}/nl/unsubscribe/{preference.unsubscribe_token}/'
    one_click_url = f'{site_url}/nl/unsubscribe/{preference.unsubscribe_token}/one-click/'
    pixel_url = f'{site_url}/nl/track/{campaign.pk}/{user.pk}/open.gif'

    body_html = _personalize(campaign.body_html, user)

    context = {
        'body_html': body_html,
        'preheader': campaign.preheader,
        'unsubscribe_url': unsubscribe_url,
        'pixel_url': pixel_url,
        'physical_address': settings.NEWSLETTER_PHYSICAL_ADDRESS,
        'campaign': campaign,
        'user': user,
    }

    html_body = render_to_string('newsletter/email_campaign.html', context)
    text_body = _html_to_text(html_body)

    msg = EmailMultiAlternatives(
        subject=campaign.subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        headers={
            'List-Unsubscribe': f'<{one_click_url}>, <{unsubscribe_url}>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        },
    )
    msg.attach_alternative(html_body, 'text/html')
    return msg


def _personalize(text, user):
    """Replace {name}, {email}, {username} placeholders with user data."""
    name = user.first_name or user.username
    replacements = {
        '{name}': name,
        '{first_name}': user.first_name or '',
        '{last_name}': user.last_name or '',
        '{username}': user.username,
        '{email}': user.email,
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def _html_to_text(html):
    """Strip HTML to plain text for the text/plain alternative."""
    text = strip_tags(html)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

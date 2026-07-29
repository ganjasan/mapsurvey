from django import template

register = template.Library()

CARD_INPUT_TYPES = {'text', 'text_line', 'number', 'choice', 'multichoice', 'range', 'rating', 'datetime'}


@register.filter
def is_card_question(field):
    question_type = getattr(field.field.widget, 'question_type', None)
    return question_type in CARD_INPUT_TYPES


@register.filter
def question_type(field):
    return getattr(field.field.widget, 'question_type', '')


@register.filter
def rating_display_style(field):
    return getattr(field.field.widget, 'display_style', 'scale_strip')


@register.filter
def get_range(count):
    return range(int(count))

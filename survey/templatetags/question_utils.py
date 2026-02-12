from django import template

register = template.Library()

CARD_INPUT_TYPES = {'text', 'text_line', 'number', 'choice', 'multichoice', 'range', 'rating'}


@register.filter
def is_card_question(field):
    question_type = getattr(field.field.widget, 'question_type', None)
    return question_type in CARD_INPUT_TYPES


@register.filter
def question_type(field):
    return getattr(field.field.widget, 'question_type', '')

from django.template import Variable, VariableDoesNotExist
from django import template


register = template.Library()

@register.filter
def hash(object, attr):
    pseudo_context = { 'object' : object }
    try:
        value = Variable('object.%s' % attr).resolve(pseudo_context)
    except VariableDoesNotExist:
        value = None

    return value
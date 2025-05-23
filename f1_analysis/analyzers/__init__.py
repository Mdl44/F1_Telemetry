import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def markdown_to_html(value):
    if value:
        return mark_safe(markdown.markdown(value, extensions=['tables']))
    return ''
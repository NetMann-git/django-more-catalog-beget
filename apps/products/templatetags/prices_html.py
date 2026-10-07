"""Только очищенное содержимое допускается к HTML-выводу."""
from django import template
from django.utils.safestring import mark_safe
from apps.products.prices_html import sanitize_prices

register = template.Library()


@register.filter
def prices_html(value: str):
    return mark_safe(sanitize_prices(value))

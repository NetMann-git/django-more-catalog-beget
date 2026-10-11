"""Метаданные публичных страниц жилья."""
from django import template
from apps.products.seo_text import plain_metadata

register = template.Library()
register.filter('seo_plain', plain_metadata)


@register.simple_tag
def housing_canonical(request, canonical_path='', page_obj=None):
    """Убрать служебные параметры, сохранив страницу публичной пагинации."""
    path = canonical_path or request.path
    if not canonical_path and page_obj and page_obj.number > 1:
        path += f'?page={page_obj.number}'
    return request.build_absolute_uri(path)

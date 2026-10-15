"""Двусторонняя навигация между категориями жилья и опубликованными картами."""
from apps.products.category_views import public_tree
from .maps import material_category_ids, material_root_categories
from .models import InformationMaterial


def category_map_links(category, categories=None):
    categories = public_tree() if categories is None else categories
    if category.pk not in {row.pk for row in categories}:
        return []
    maps = list(InformationMaterial.objects.filter(is_active=True, kind='map').prefetch_related('map_categories'))
    maps.sort(key=lambda row: (row.joomla_id == 841, row.title.casefold(), row.pk))
    links = []
    for material in maps:
        selected = material_category_ids(material, categories)
        if selected is not None and category.pk in selected:
            links.append({'title': material.title, 'url': material.get_absolute_url() + '#housing-resort-map'})
    return links


def map_category_links(material):
    if not material.is_active:
        return []
    return [{'title': row.title, 'url': row.get_absolute_url()}
            for row in (material_root_categories(material) or [])]

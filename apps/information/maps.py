"""Карты курортов: явная связь исходных материалов с категориями Joomla."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from apps.products.category_views import public_tree
from apps.products.map_data import coordinate_pair
from apps.products.models import Product

MAP_REGIONS = {
    882: (84,), 866: (82,), 865: (80,), 864: (81,),
    841: (73, 77, 114, 79, 80, 81, 85, 82, 83),
    840: (86,), 839: (85,), 838: (114,), 837: (77,), 836: (73,),
}


def material_products(material):
    if material.kind != 'map':
        return None
    categories = public_tree()
    if material.map_mode == 'categories':
        chosen = set(material.map_categories.values_list('pk', flat=True)) if material.pk else set()
        selected = {row.pk for row in categories if row.pk in chosen}
    else:
        regions = MAP_REGIONS.get(material.joomla_id)
        if regions is None:
            return None
        selected = {row.pk for row in categories if row.joomla_id in regions}
    while True:
        expanded = selected | {row.pk for row in categories if row.parent_id in selected}
        if expanded == selected:
            break
        selected = expanded
    return Product.objects.filter(is_active=True).filter(
        Q(category_id__in=selected) | Q(categories__pk__in=selected)
    ).distinct().order_by('title', 'pk')


def material_map(material):
    products = material_products(material)
    if products is None:
        return None
    points = []
    for product in products:
        try:
            marker = coordinate_pair(product.map_coordinates)
        except ValidationError:
            continue
        if marker is not None:
            points.append({'coordinates': marker, 'title': product.title,
                           'address': product.address, 'url': product.get_absolute_url()})
    return {'points': points, 'tile_url': settings.MAP_EDITOR_TILE_URL,
            'attribution': settings.MAP_EDITOR_TILE_ATTRIBUTION}

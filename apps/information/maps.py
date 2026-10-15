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


def material_category_ids(material, categories=None):
    if material.kind != 'map':
        return None
    categories = public_tree() if categories is None else categories
    if material.map_mode == 'categories':
        chosen = {row.pk for row in material.map_categories.all()} if material.pk else set()
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
    return selected


def material_products(material):
    selected = material_category_ids(material)
    if selected is None:
        return None
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
            points.append({'id': product.pk, 'coordinates': marker, 'title': product.title,
                           'address': product.address, 'url': product.get_absolute_url()})
    return {'points': points, 'tile_url': settings.MAP_EDITOR_TILE_URL,
            'attribution': settings.MAP_EDITOR_TILE_ATTRIBUTION}


def product_map_links(product):
    """Только карты, в публичную выборку которых входит текущий объект с меткой."""
    from .models import InformationMaterial
    if not product.is_active:
        return []
    try:
        if coordinate_pair(product.map_coordinates) is None:
            return []
    except ValidationError:
        return []
    categories = public_tree()
    assigned = {row.pk for row in product.categories.all()}
    if product.category_id:
        assigned.add(product.category_id)
    links = []
    materials = list(InformationMaterial.objects.filter(kind='map', is_active=True).prefetch_related('map_categories'))
    materials.sort(key=lambda row: (row.joomla_id == 841, row.title.casefold(), row.pk))
    for material in materials:
        selected = material_category_ids(material, categories)
        if selected is not None and selected & assigned:
            links.append({'title': material.title, 'url': material.get_absolute_url() + f'?object={product.pk}#housing-resort-map'})
    return links


def select_map_point(data, value):
    """Не раскрывать объекты вне текущей публичной карты через query-параметр."""
    if data is None:
        return None
    selected = next((point for point in data['points'] if str(point['id']) == value), None)
    return {**data, 'selected_id': selected['id'] if selected else None, 'selected_point': selected}

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


def material_root_categories(material, categories=None):
    """Публичные категории, явно заданные в настройке карты, без потомков."""
    if material.kind != 'map':
        return None
    categories = public_tree() if categories is None else categories
    if material.map_mode == 'categories':
        chosen = {row.pk for row in material.map_categories.all()} if material.pk else set()
        return [row for row in categories if row.pk in chosen]
    regions = MAP_REGIONS.get(material.joomla_id)
    if regions is None:
        return None
    return [row for row in categories if row.joomla_id in regions]


def material_category_ids(material, categories=None):
    if material.kind != 'map':
        return None
    categories = public_tree() if categories is None else categories
    roots = material_root_categories(material, categories)
    if roots is None:
        return None
    selected = {row.pk for row in roots}
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
    types = {}
    for product in products.select_related('brand'):
        try:
            marker = coordinate_pair(product.map_coordinates)
        except ValidationError:
            continue
        if marker is not None:
            key = str(product.brand_id) if product.brand_id else 'untyped'
            label = product.brand.name if product.brand_id else 'Тип не указан'
            if key not in types:
                types[key] = {'value': key, 'label': label, 'count': 0,
                              'order': product.brand.sort_order if product.brand_id else 0}
            types[key]['count'] += 1
            points.append({'housing_type': key, 'housing_type_label': label, 'id': product.pk, 'coordinates': marker, 'title': product.title,
                           'address': product.address, 'url': product.get_absolute_url()})
    housing_types = sorted(types.values(), key=lambda row: (row['value'] == 'untyped', row['order'], row['label'].casefold(), row['value']))
    return {'points': points, 'housing_types': housing_types, 'tile_url': settings.MAP_EDITOR_TILE_URL,
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

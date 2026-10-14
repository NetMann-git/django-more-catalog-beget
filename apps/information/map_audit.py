"""Проверка состава карт без изменения базы и сетевых запросов."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.products.category_views import public_tree
from apps.products.map_data import coordinate_pair
from apps.products.models import Category
from .maps import MAP_REGIONS, material_products
from .models import InformationMaterial


def audit_maps():
    rows, issues, warnings = [], [], []
    checked_ids, missing_ids, invalid_ids = set(), set(), set()
    visible_ids = {row.pk for row in public_tree()}
    all_categories = {row.joomla_id: row for row in Category.objects.all() if row.joomla_id is not None}
    for material in InformationMaterial.objects.filter(kind='map', is_active=True).order_by('pk'):
        row = {'id': material.pk, 'joomla_id': material.joomla_id, 'title': material.title,
               'url': material.get_absolute_url(), 'mode': material.map_mode,
               'objects_in_categories': 0, 'points': 0, 'missing_coordinates': [],
               'invalid_coordinates': [], 'coincident_groups': 0}
        def issue(code, **details):
            issues.append({'material_id': material.pk, 'code': code, **details})
        def warning(code, **details):
            warnings.append({'material_id': material.pk, 'code': code, **details})
        if material.map_mode not in ('legacy', 'categories'):
            issue('unknown_map_mode')
            rows.append(row)
            continue
        if material.map_mode == 'legacy':
            regions = MAP_REGIONS.get(material.joomla_id)
            if regions is None:
                issue('legacy_map_not_configured')
                rows.append(row)
                continue
            absent = [region for region in regions if region not in all_categories]
            if absent:
                issue('missing_legacy_categories', joomla_ids=absent)
            hidden = [all_categories[region].pk for region in regions
                      if region in all_categories and all_categories[region].pk not in visible_ids]
        else:
            chosen = set(material.map_categories.values_list('pk', flat=True))
            hidden = sorted(chosen - visible_ids)
            if not chosen:
                warning('no_categories_selected')
        if hidden:
            warning('categories_not_public', category_ids=hidden)
        coordinates = {}
        for product in material_products(material):
            checked_ids.add(product.pk)
            row['objects_in_categories'] += 1
            try:
                marker = coordinate_pair(product.map_coordinates)
            except ValidationError:
                invalid_ids.add(product.pk)
                row['invalid_coordinates'].append(product.pk)
                continue
            if marker is None:
                missing_ids.add(product.pk)
                row['missing_coordinates'].append(product.pk)
                continue
            row['points'] += 1
            key = tuple(Decimal(value) for value in marker)
            coordinates[key] = coordinates.get(key, 0) + 1
        row['coincident_groups'] = sum(count > 1 for count in coordinates.values())
        if row['invalid_coordinates']:
            issue('invalid_marker_coordinates', product_ids=row['invalid_coordinates'])
        if row['missing_coordinates']:
            warning('missing_marker_coordinates', product_ids=row['missing_coordinates'])
        if not row['points']:
            warning('empty_map')
        rows.append(row)
    return {'published_maps': len(rows), 'unique_objects_checked': len(checked_ids),
            'unique_objects_without_coordinates': len(missing_ids),
            'unique_objects_with_invalid_coordinates': len(invalid_ids),
            'maps': rows, 'issues': issues, 'warnings': warnings, 'ok': not issues}

"""Диагностика категорий опубликованного жилья без изменения привязок."""
from collections import Counter
from apps.information.maps import material_products
from apps.information.models import InformationMaterial
from .category_views import public_tree
from .models import Category, Product


def category_coverage():
    categories = {row.pk: row for row in Category.objects.all()}
    public = {row.pk for row in public_tree()}
    covered, maps = set(), []
    for material in InformationMaterial.objects.filter(kind='map', is_active=True).order_by('pk'):
        queryset = material_products(material)
        ids = set(queryset.values_list('pk', flat=True)) if queryset is not None else set()
        covered.update(ids)
        maps.append({'id': material.pk, 'title': material.title, 'objects': len(ids), 'configured': queryset is not None})
    counts, outside_counts, reasons = Counter(), Counter(), Counter()
    outside = []
    published = list(Product.objects.filter(is_active=True).prefetch_related('categories').order_by('pk'))
    for product in published:
        assigned = {category.pk for category in product.categories.all()}
        if product.category_id is not None:
            assigned.add(product.category_id)
        counts.update(assigned)
        if product.pk in covered:
            continue
        outside_counts.update(assigned)
        reason = ('no_categories' if not assigned else
                  'no_public_categories' if not (assigned & public) else 'outside_map_categories')
        reasons[reason] += 1
        outside.append({'id': product.pk, 'joomla_id': product.joomla_id, 'title': product.title,
            'url': product.get_absolute_url(), 'admin_url': f'/admin/products/product/{product.pk}/change/',
            'primary_category_id': product.category_id, 'category_ids': sorted(assigned), 'reason': reason})
    def path(category):
        result, visited = [], set()
        while category is not None and category.pk not in visited:
            visited.add(category.pk)
            result.append(category.title)
            category = categories.get(category.parent_id)
        if category is not None:
            result.append('[цикл]')
        return ' / '.join(reversed(result))
    category_rows = [{'id': row.pk, 'joomla_id': row.joomla_id, 'title': row.title,
        'path': path(row), 'parent_id': row.parent_id, 'public': row.pk in public,
        'published_objects_assigned': counts[row.pk], 'objects_outside_maps': outside_counts[row.pk]}
        for row in categories.values() if counts[row.pk]]
    category_rows.sort(key=lambda row: (-row['objects_outside_maps'], row['path'], row['id']))
    return {'published_objects': len(published), 'published_maps': len(maps),
        'objects_covered_by_maps': len(covered), 'objects_outside_maps': len(outside),
        'outside_map_reasons': {key: reasons[key] for key in
            ('no_categories', 'no_public_categories', 'outside_map_categories')},
        'maps': maps, 'categories': category_rows, 'outside_objects': outside,
        'coverage_complete': not outside}

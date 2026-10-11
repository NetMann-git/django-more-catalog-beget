"""Навигация объекта только по публичным категориям жилья."""
from .category_views import public_tree


def category_navigation(product):
    categories = public_tree()
    by_id = {category.pk: category for category in categories}
    assigned = set(product.categories.values_list('pk', flat=True))
    if product.category_id:
        assigned.add(product.category_id)
    links = [category for category in categories if category.pk in assigned]
    breadcrumbs = []
    current = by_id.get(product.category_id)
    while current is not None:
        breadcrumbs.append(current)
        current = by_id.get(current.parent_id)
    return {'housing_categories': links, 'housing_category_path': list(reversed(breadcrumbs))}

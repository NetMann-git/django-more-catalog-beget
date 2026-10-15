"""Применить только проверенные дополнительные привязки; основные поля не сохраняются."""
from django.core.management.base import CommandError
from django.db import transaction
from apps.products.category_views import public_tree
from apps.products.models import Product
from apps.products.region_proposals import REGIONS, proposal, snapshot_hash


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get('schema') != 2 or plan.get('applied') is not False:
        raise CommandError('Пересоздайте план командой plan_housing_region_categories из шага 69.')
    rows = plan.get('items')
    if not isinstance(rows, list) or plan.get('objects_outside_maps') != len(rows):
        raise CommandError('Неверная структура или количество записей плана.')
    ids = [row.get('id') if isinstance(row, dict) else None for row in rows]
    if any(type(pk) is not int or pk <= 0 for pk in ids) or len(set(ids)) != len(ids):
        raise CommandError('В плане есть неверные или повторяющиеся ID объектов.')
    categories = {row.joomla_id: row for row in public_tree() if row.joomla_id in REGIONS}
    products = {product.pk: product for product in Product.objects.filter(pk__in=ids).prefetch_related('categories')}
    changes, unchanged = [], []
    for row in rows:
        pk = row['id']
        product = products.get(pk)
        if product is None or not product.is_active:
            raise CommandError(f'Объект {pk} отсутствует или скрыт. Пересоздайте план.')
        if row.get('status') != 'proposed':
            raise CommandError(f'Объект {pk} требует ручной проверки. План не применён.')
        fresh = proposal(product, categories)
        target = fresh['suggested_category_id']
        if fresh['status'] != 'proposed' or target != row.get('suggested_category_id'):
            raise CommandError(f'Предложение для объекта {pk} изменилось. Пересоздайте план.')
        old_ids = row.get('existing_category_ids')
        if not isinstance(old_ids, list) or any(type(value) is not int for value in old_ids) or target in old_ids:
            raise CommandError(f'Некорректные исходные категории объекта {pk}.')
        current_ids = set(fresh['existing_category_ids'])
        if current_ids not in (set(old_ids), set(old_ids) | {target}):
            raise CommandError(f'Категории объекта {pk} изменились. Пересоздайте план.')
        if snapshot_hash(product, old_ids) != row.get('snapshot_sha256'):
            raise CommandError(f'Состояние объекта {pk} изменилось. Пересоздайте план.')
        if row.get('primary_category_id') != product.category_id or row.get('url') != product.get_absolute_url():
            raise CommandError(f'Основная категория или URL объекта {pk} изменились.')
        if target in current_ids:
            unchanged.append(pk)
        else:
            changes.append((product, target))
    return changes, unchanged


def apply_plan(plan):
    with transaction.atomic():
        changes, unchanged = validate_plan(plan)
        for product, target in changes:
            product.categories.add(target)
    return {'added_links': len(changes), 'already_applied': len(unchanged),
            'added': [{'product_id': product.pk, 'category_id': target} for product, target in changes]}

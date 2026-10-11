"""ID опубликованных объектов для пользовательских списков и счётчиков."""
from .models import Product


def unique_product_ids(values):
    """Убрать дубли и некорректные значения, сохранив порядок списка."""
    if not isinstance(values, (list, tuple)):
        return []
    result = []
    seen = set()
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            continue
        try:
            pk = int(value)
        except (ValueError, TypeError):
            continue
        if pk > 0 and pk not in seen:
            seen.add(pk)
            result.append(pk)
    return result


def active_product_ids(values):
    """Исключить скрытые и удалённые объекты без изменения исходного списка."""
    ids = unique_product_ids(values)
    active = set(Product.objects.filter(pk__in=ids, is_active=True).values_list('pk', flat=True))
    return [pk for pk in ids if pk in active]

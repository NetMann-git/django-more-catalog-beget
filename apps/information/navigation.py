"""Пути категорий без SQL-запроса на каждый уровень и без случайного выбора категории."""


def category_path(category_id, categories):
    by_id = {row.pk: row for row in categories}
    result, visited = [], set()
    while category_id is not None:
        row = by_id.get(category_id)
        if row is None or category_id in visited or not row.is_published:
            return []
        visited.add(category_id)
        result.append(row)
        category_id = row.parent_id
    return list(reversed(result))


def material_navigation(material, public_rows, assigned_rows):
    assigned = {row.pk for row in assigned_rows}
    if material.primary_category_id:
        assigned.add(material.primary_category_id)
    return {'material_categories': [row for row in public_rows if row.pk in assigned],
            'material_breadcrumb_categories': category_path(material.primary_category_id, public_rows)}

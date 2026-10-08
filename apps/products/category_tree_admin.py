"""Дерево в стандартном списке Django Admin без изменения модели."""
from django.contrib.admin.views.main import ChangeList
from django.urls import reverse
from django.utils.html import format_html


def arrange_categories(categories):
    """Построить дерево видимых строк; защититься от повреждённых циклов."""
    categories = list(categories)
    by_id = {obj.pk: obj for obj in categories}
    children = {}
    for obj in categories:
        parent = obj.parent_id if obj.parent_id in by_id else None
        children.setdefault(parent, []).append(obj)
    for group in children.values():
        group.sort(key=lambda obj: (obj.sort_order, obj.title.casefold(), obj.pk))
    result, visited = [], set()

    def walk(roots):
        stack = [(obj, ()) for obj in reversed(roots)]
        while stack:
            obj, ancestors = stack.pop()
            if obj.pk in visited:
                continue
            visited.add(obj.pk)
            obj.tree_depth = len(ancestors)
            obj.tree_ancestors = ancestors
            obj.tree_has_children = any(child.pk not in visited for child in children.get(obj.pk, []))
            result.append(obj)
            stack.extend((child, (*ancestors, obj.pk)) for child in reversed(children.get(obj.pk, [])))

    walk(children.get(None, []))
    # Некорректные циклы не должны скрывать записи из админки.
    for obj in sorted(categories, key=lambda obj: (obj.sort_order, obj.title.casefold(), obj.pk)):
        if obj.pk not in visited:
            walk([obj])
    return result


class CategoryTreeChangeList(ChangeList):
    """Не разрывать ветки дерева пагинацией; поиск и действия остаются штатными."""

    def get_results(self, request):
        super().get_results(request)
        self.result_list = arrange_categories(self.queryset)
        self.multi_page = False
        self.can_show_all = True


def category_tree_title(obj):
    """Название, ссылка редактирования и отдельная кнопка раскрытия."""
    ancestors = getattr(obj, "tree_ancestors", ())
    depth = getattr(obj, "tree_depth", 0)
    if getattr(obj, "tree_has_children", False):
        toggle = format_html(
            '<button type="button" class="category-tree-toggle" aria-expanded="true" '
            'aria-label="Свернуть ветку: {}">▾</button>', obj.title,
        )
    else:
        toggle = format_html('<span class="category-tree-leaf" aria-hidden="true">·</span>')
    return format_html(
        '<span class="category-tree-node" data-node="{}" data-ancestors="{}" '
        'style="--tree-depth:{}">{}<a href="{}">{}</a></span>',
        obj.pk, ",".join(str(pk) for pk in ancestors), depth, toggle,
        reverse("admin:products_category_change", args=[obj.pk]), obj.title,
    )

"""Отбор материалов по основной/M2M-категории с явным выбором глубины."""
import re
from django.contrib import admin
from django.db.models import Q
from apps.products.category_tree_admin import arrange_categories
from .models import InformationCategory


class MaterialCategoryFilter(admin.SimpleListFilter):
    title = 'Категория материалов'
    parameter_name = 'material_category'

    def lookups(self, request, model_admin):
        self.category_rows = arrange_categories(InformationCategory.objects.all())
        return [('none', 'Без категории')] + [
            (str(row.pk), '— ' * row.tree_depth + row.title) for row in self.category_rows]

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset
        if value == 'none':
            return queryset.filter(primary_category__isnull=True, categories__isnull=True).distinct()
        if not re.fullmatch(r'[1-9][0-9]{0,18}', value):
            return queryset.none()
        pk = int(value)
        if pk not in {row.pk for row in self.category_rows}:
            return queryset.none()
        selected = {pk}
        if request.GET.get('category_scope') != 'direct':
            while True:
                expanded = selected | {row.pk for row in self.category_rows if row.parent_id in selected}
                if expanded == selected:
                    break
                selected = expanded
        return queryset.filter(Q(primary_category_id__in=selected) | Q(categories__pk__in=selected)).distinct()


class MaterialCategoryScopeFilter(admin.SimpleListFilter):
    title = 'Глубина категории'
    parameter_name = 'category_scope'

    def lookups(self, request, model_admin):
        return [('tree', 'С подкатегориями'), ('direct', 'Только выбранная')]

    def choices(self, changelist):
        current = 'direct' if self.value() == 'direct' else 'tree'
        for value, label in self.lookup_choices:
            yield {'selected': current == value,
                   'query_string': changelist.get_query_string({self.parameter_name: value}),
                   'display': label}

    def queryset(self, request, queryset):
        return queryset

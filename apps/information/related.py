"""Материалы того же типа с общей публичной категорией, без случайной подстановки."""
from django.db.models import Q
from .models import InformationMaterial


LIMIT = 3


def related_materials(material, visible_ids, category_ids=None):
    if not material.is_active:
        return []
    assigned = set(category_ids) if category_ids is not None else {row.pk for row in material.categories.all()}
    if material.primary_category_id:
        assigned.add(material.primary_category_id)
    shared = assigned & set(visible_ids)
    if not shared:
        return []
    return list(InformationMaterial.objects.filter(is_active=True, kind=material.kind).exclude(pk=material.pk)
        .filter(Q(categories__pk__in=shared) | Q(primary_category_id__in=shared)).distinct()
        .defer('source', 'body', 'extra_body', 'html_insert').order_by('title', 'pk')[:LIMIT])

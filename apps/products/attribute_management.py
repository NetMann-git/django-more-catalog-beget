"""Управление справочником характеристик из кабинета менеджера."""

from django.contrib import messages
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.users.constants import ROLE_ADMIN, ROLE_MANAGER
from apps.users.decorators import role_required

from .attribute_forms import AttributeTypeForm, AttributeValueForm
from .cache import CatalogCache
from .models import AttributeType, AttributeValue


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_type_list_manage(request):
    """Список типов и количество значений для каждого типа."""
    types = AttributeType.objects.annotate(
        values_count=Count("values", distinct=True),
        products_count=Count("product_attributes", distinct=True),
    ).order_by("name")
    return render(request, "products/attribute_type_list.html", {"types": types})


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_type_create(request):
    """Создать тип характеристики и перейти к его значениям."""
    form = AttributeTypeForm(request.POST if request.method == "POST" else None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        attribute_type = form.save()
        CatalogCache.clear_catalog()
        messages.success(request, "Тип характеристики добавлен.")
        return redirect("catalog:attribute_type_edit", type_id=attribute_type.pk)
    return render(request, "products/attribute_type_form.html", {
        "form": form, "attribute_type": None,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_type_edit(request, type_id):
    """Редактировать имя и тип данных, не меняя slug."""
    attribute_type = get_object_or_404(AttributeType, pk=type_id)
    form = AttributeTypeForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=attribute_type)
    if request.method == "POST" and form.is_valid():
        form.save()
        CatalogCache.clear_catalog()
        messages.success(request, "Тип характеристики сохранён.")
        return redirect("catalog:attribute_type_edit", type_id=type_id)
    return render(request, "products/attribute_type_form.html", {
        "form": form,
        "attribute_type": attribute_type,
        "values": attribute_type.values.select_related("attribute_type"),
        "value_form": AttributeValueForm(attribute_type=attribute_type),
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_type_delete(request, type_id):
    """Удалить только тип, который не используется автомобилями."""
    attribute_type = get_object_or_404(AttributeType, pk=type_id)
    if request.method == "POST":
        try:
            attribute_type.delete()
        except ProtectedError:
            messages.error(request, "Тип используется автомобилями. Сначала удалите связи с товарами.")
            return redirect("catalog:attribute_type_edit", type_id=type_id)
        CatalogCache.clear_catalog()
        messages.success(request, "Тип характеристики удалён.")
        return redirect("catalog:attribute_type_list_manage")
    return render(request, "products/attribute_confirm_delete.html", {
        "title": "Удалить тип характеристики?",
        "name": attribute_type.name,
        "return_url": "catalog:attribute_type_edit",
        "return_id": type_id,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def attribute_value_create(request, type_id):
    """Добавить значение конкретному типу."""
    attribute_type = get_object_or_404(AttributeType, pk=type_id)
    value_form = AttributeValueForm(
        request.POST, request.FILES, attribute_type=attribute_type,
    )
    if value_form.is_valid():
        value = value_form.save(commit=False)
        value.attribute_type = attribute_type
        value.save()
        CatalogCache.clear_catalog()
        messages.success(request, "Значение добавлено.")
        return redirect("catalog:attribute_type_edit", type_id=type_id)
    return render(request, "products/attribute_type_form.html", {
        "form": AttributeTypeForm(instance=attribute_type),
        "attribute_type": attribute_type,
        "values": attribute_type.values.select_related("attribute_type"),
        "value_form": value_form,
    }, status=400)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_value_edit(request, type_id, value_id):
    """Изменить значение, сохранив ссылки на него в товарах."""
    value = get_object_or_404(
        AttributeValue, pk=value_id, attribute_type_id=type_id,
    )
    form = AttributeValueForm(
        request.POST if request.method == "POST" else None, request.FILES or None, attribute_type=value.attribute_type,
        instance=value,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        CatalogCache.clear_catalog()
        messages.success(request, "Значение сохранено.")
        return redirect("catalog:attribute_type_edit", type_id=type_id)
    return render(request, "products/attribute_value_form.html", {
        "form": form, "attribute_type": value.attribute_type,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_value_delete(request, type_id, value_id):
    """Не удалять значение, назначенное хотя бы одному автомобилю."""
    value = get_object_or_404(
        AttributeValue, pk=value_id, attribute_type_id=type_id,
    )
    if request.method == "POST":
        try:
            value.delete()
        except ProtectedError:
            messages.error(request, "Значение используется автомобилями и не может быть удалено.")
            return redirect("catalog:attribute_type_edit", type_id=type_id)
        CatalogCache.clear_catalog()
        messages.success(request, "Значение удалено.")
        return redirect("catalog:attribute_type_edit", type_id=type_id)
    return render(request, "products/attribute_confirm_delete.html", {
        "title": "Удалить значение характеристики?",
        "name": value.value,
        "return_url": "catalog:attribute_type_edit",
        "return_id": type_id,
    })

"""Общий выбор множественных характеристик для админки и менеджера."""

from django import forms
from django.db import transaction

from .models import AttributeType, AttributeValue, Product, ProductAttribute


class MultipleAttributeMixin:
    """Сохранение флажков меняет только связи выбранных типов."""

    multiple_types = ()

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = (
            product if product is not None else getattr(self, "instance", None)
        )
        if self.product and self.product.pk:
            for kind in self.multiple_types:
                self.initial[f"multiple_attribute_{kind.pk}"] = list(
                    self.product.attributes.filter(attribute_type=kind).values_list(
                        "attribute_value_id", flat=True
                    )
                )

    def save_multiple(self, product):
        """Сохранить выбор без пересоздания оставшихся строк характеристик."""
        if not self.is_valid():
            raise ValueError("Нельзя сохранить неверный выбор характеристик.")
        with transaction.atomic():
            Product.objects.select_for_update().get(pk=product.pk)
            for kind in self.multiple_types:
                values = self.cleaned_data[f"multiple_attribute_{kind.pk}"]
                selected = {value.pk for value in values}
                rows = product.attributes.filter(attribute_type=kind)
                rows.exclude(attribute_value_id__in=selected).delete()
                existing = set(rows.values_list("attribute_value_id", flat=True))
                for value in values:
                    if value.pk not in existing:
                        ProductAttribute.objects.create(
                            product=product,
                            attribute_type=kind,
                            attribute_value=value,
                            sort_order=value.sort_order,
                        )


class MultipleAttributeForm(MultipleAttributeMixin, forms.Form):
    """Форма менеджера, сохраняемая вместе с одиночными характеристиками."""


class MultipleProductAdminForm(MultipleAttributeMixin, forms.ModelForm):
    """Обычная форма Product с дополнительными полями флажков."""

    class Meta:
        model = Product
        fields = "__all__"


def multiple_types():
    """Показывать только типы со включённым множественным выбором."""
    return list(AttributeType.objects.filter(allow_multiple=True, data_type="choice"))


def build_multiple_form(base=MultipleAttributeForm, kinds=None):
    """Создать декларативные поля, чтобы админка распознала их в fieldsets."""
    kinds = multiple_types() if kinds is None else kinds
    attributes = {"multiple_types": tuple(kinds), "__module__": __name__}
    for kind in kinds:
        attributes[f"multiple_attribute_{kind.pk}"] = forms.ModelMultipleChoiceField(
            queryset=AttributeValue.objects.filter(attribute_type=kind),
            label=kind.name,
            required=False,
            widget=forms.CheckboxSelectMultiple(
                attrs={"class": "multiple-attributes__choices"}
            ),
            help_text="Отметьте подходящие значения. Снятие флажка удаляет связь с объектом.",
        )
    return type("ObjectMultipleAttributesForm", (base,), attributes)

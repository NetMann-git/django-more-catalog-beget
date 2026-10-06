"""Проверка набора характеристик в админке и панели менеджера."""

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Product, ProductAttribute
from .product_attribute_forms import ProductAttributeForm


class ProductAttributeFormSet(BaseInlineFormSet):
    """Reject identifiers that do not belong to the edited product."""

    def add_fields(self, form, index):
        """Проверка одиночности выполняется для всего набора, а не одной строки."""
        super().add_fields(form, index)
        form.instance._validated_in_formset = True

    def clean(self) -> None:
        """Проверить конечный набор, включая записи, не присланные в POST."""
        super().clean()
        if any(self.errors):
            return
        rows = []
        submitted_ids = set()
        for form in self.forms:
            data = form.cleaned_data
            if not data:
                continue
            record = data.get("id")
            if record:
                if record.product_id != self.instance.pk:
                    raise forms.ValidationError(
                        "Характеристика принадлежит другому объекту."
                    )
                if record.pk in submitted_ids:
                    raise forms.ValidationError(
                        "Одна запись характеристики прислана несколько раз."
                    )
                submitted_ids.add(record.pk)
            if data.get("DELETE"):
                continue
            kind = data.get("attribute_type")
            if kind is None:
                continue
            value = data.get("attribute_value")
            key = value.value if value else data.get("free_value", "").strip()
            rows.append((kind, key))
        if self.instance.pk:
            for record in self.instance.attributes.exclude(
                pk__in=submitted_ids
            ).select_related("attribute_type", "attribute_value"):
                rows.append(
                    (
                        record.attribute_type,
                        record.attribute_value.value if record.attribute_value else "",
                    )
                )
        seen_types = set()
        seen_values = set()
        for kind, key in rows:
            if not kind.allow_multiple and kind.pk in seen_types:
                raise forms.ValidationError(
                    f"«{kind.name}»: разрешено только одно значение."
                )
            pair = (kind.pk, key)
            if pair in seen_values:
                raise forms.ValidationError(
                    f"«{kind.name}»: одно значение выбрано повторно."
                )
            seen_types.add(kind.pk)
            seen_values.add(pair)


ManagerAttributeFormSet = inlineformset_factory(
    Product,
    ProductAttribute,
    form=ProductAttributeForm,
    formset=ProductAttributeFormSet,
    fields=("attribute_type", "attribute_value", "free_value", "sort_order"),
    extra=1,
    can_delete=True,
)


class SingleProductAttributeFormSet(ProductAttributeFormSet):
    """В строковом редакторе остаются только одиночные типы."""

    def add_fields(self, form, index):
        """Сохранить общую форму, ограничив её одиночными типами."""
        super().add_fields(form, index)
        form.fields["attribute_type"].queryset = form.fields[
            "attribute_type"
        ].queryset.filter(allow_multiple=False)

    def get_queryset(self):
        return super().get_queryset().filter(attribute_type__allow_multiple=False)


ManagerSingleAttributeFormSet = inlineformset_factory(
    Product,
    ProductAttribute,
    form=ProductAttributeForm,
    formset=SingleProductAttributeFormSet,
    fields=("attribute_type", "attribute_value", "free_value", "sort_order"),
    extra=1,
    can_delete=True,
)

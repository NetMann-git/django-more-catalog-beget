"""Typed input for product attributes with compatible value storage."""

from typing import Any

from django import forms

from .cache import CatalogCache
from .models import AttributeType, AttributeValue, ProductAttribute


class AttributeTypeSelect(forms.Select):
    """Expose the input kind without embedding unsafe JSON in templates."""

    def create_option(
        self, name: str, value: Any, label: Any, selected: bool,
        index: int, **kwargs: Any,
    ) -> dict[str, Any]:
        option = super().create_option(name, value, label, selected, index, **kwargs)
        if hasattr(value, 'instance'):
            option['attrs']['data-kind'] = value.instance.data_type
            option['attrs']['data-slug'] = value.instance.slug
            option['attrs']['data-icon'] = value.instance.icon.url if value.instance.icon else ''
        return option


class AttributeValueSelect(forms.Select):
    """Expose each value's type for dependent dropdowns."""

    def create_option(
        self, name: str, value: Any, label: Any, selected: bool,
        index: int, **kwargs: Any,
    ) -> dict[str, Any]:
        option = super().create_option(name, value, label, selected, index, **kwargs)
        if hasattr(value, 'instance'):
            option['attrs']['data-owner'] = value.instance.attribute_type_id
            icon = value.instance.effective_icon
            option['attrs']['data-icon'] = icon.url if icon else ''
        return option


class ProductAttributeForm(forms.ModelForm):
    """Accept numeric/text input or a validated choice for one product."""

    attribute_type = forms.ModelChoiceField(
        queryset=AttributeType.objects.all(), label='Тип характеристики',
        widget=AttributeTypeSelect(attrs={
            'class': 'form-control', 'data-attribute-type': '',
        }),
    )
    attribute_value = forms.ModelChoiceField(
        queryset=AttributeValue.objects.select_related('attribute_type'),
        required=False, label='Значение из списка',
        widget=AttributeValueSelect(attrs={
            'class': 'form-control', 'data-attribute-choice': '',
        }),
    )
    free_value = forms.CharField(
        required=False, max_length=255, label='Число или текст',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'data-attribute-input': '',
        }),
    )

    class Meta:
        model = ProductAttribute
        fields = ('attribute_type', 'attribute_value', 'free_value', 'sort_order')

    class Media:
        js = ('products/js/product-attribute-inputs.js',)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields['sort_order'].required = False
        if (self.instance.attribute_value_id
                and self.instance.attribute_type.data_type != 'choice'):
            self.initial['free_value'] = self.instance.attribute_value.value

    def clean_sort_order(self) -> int:
        """Preserve ordering when the manager's compact form omits it."""
        value = self.cleaned_data.get('sort_order')
        return self.instance.sort_order if value is None else value

    def clean(self) -> dict[str, Any]:
        """Validate against the selected type on the server as well as in UI."""
        cleaned = super().clean()
        kind = cleaned.get('attribute_type')
        if kind is None:
            return cleaned
        if kind.data_type == 'choice':
            value = cleaned.get('attribute_value')
            if value is None:
                self.add_error('attribute_value', 'Выберите значение из списка.')
            elif value.attribute_type_id != kind.pk:
                self.add_error('attribute_value', 'Значение относится к другому типу.')
            return cleaned

        raw = cleaned.get('free_value', '').strip()
        if not raw:
            self.add_error('free_value', 'Введите значение характеристики.')
        elif kind.data_type == 'number':
            try:
                number = forms.DecimalField(
                    max_digits=18, decimal_places=6,
                ).clean(raw.replace(',', '.'))
                if kind.slug == 'mileage' and (
                    number < 0 or number != number.to_integral_value()
                ):
                    raise forms.ValidationError('Пробег должен быть целым числом от 0.')
                cleaned['free_value'] = format(number.normalize(), 'f')
            except forms.ValidationError as error:
                self.add_error('free_value', error)
        cleaned['attribute_value'] = None
        return cleaned

    def save(self, commit: bool = True) -> ProductAttribute:
        """Reuse existing value records so catalog filters remain compatible."""
        instance = super().save(commit=False)
        if instance.attribute_type.data_type != 'choice':
            instance.attribute_value, _ = AttributeValue.objects.get_or_create(
                attribute_type=instance.attribute_type,
                value=self.cleaned_data['free_value'],
            )
        if commit:
            instance.save()
            self.save_m2m()
            CatalogCache.clear_catalog()
        return instance

"""Формы справочника автомобильных характеристик для менеджера."""

from django import forms

from .manager_slugs import AutoSlugMixin
from .models import AttributeType, AttributeValue


class AttributeTypeForm(AutoSlugMixin, forms.ModelForm):
    """Создание типа; используемый фильтрами slug нельзя менять позднее."""

    slug_source = "name"
    slug = forms.SlugField(
        required=False, label="Код (slug)",
        help_text="Автоматически из названия. После сохранения изменить нельзя.",
    )

    class Meta:
        model = AttributeType
        fields = ("name", "slug", "data_type", "icon")
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control", "data-slug-source": "true",
            }),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "data_type": forms.Select(attrs={"class": "form-control"}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop("slug")
        else:
            self.fields["slug"].widget.attrs.update({
                "class": "form-control", "data-slug-target": "true",
            })


class AttributeValueForm(forms.ModelForm):
    """Значение выбранного типа с проверкой повторов."""

    class Meta:
        model = AttributeValue
        fields = ("value", "sort_order", "icon")
        widgets = {
            "value": forms.TextInput(attrs={"class": "form-control"}),
            "sort_order": forms.NumberInput(attrs={
                "class": "form-control", "min": 0,
            }),
        }

    def __init__(self, *args, attribute_type: AttributeType, **kwargs):
        super().__init__(*args, **kwargs)
        self.attribute_type = attribute_type

    def clean_value(self) -> str:
        """Не создавать одинаковых значений в пределах одного типа."""
        value = self.cleaned_data["value"].strip()
        if not value:
            raise forms.ValidationError("Введите значение характеристики.")
        duplicates = AttributeValue.objects.filter(
            attribute_type=self.attribute_type, value=value,
        ).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError("Такое значение уже есть у этого типа.")
        return value

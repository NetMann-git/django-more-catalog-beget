"""Проверки множественных удобств и сохранения одиночных характеристик."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.products.attribute_formsets import ManagerAttributeFormSet
from apps.products.models import (
    AttributeType,
    AttributeValue,
    Product,
    ProductAttribute,
)


class MultipleAttributeTests(TestCase):
    """Проверка конечного набора значений при сохранении форм."""

    def setUp(self):
        self.product = Product.objects.create(title="Дом", slug="house", price=1)
        self.kind = AttributeType.objects.create(
            name="Удобства", slug="amenities", data_type="choice", allow_multiple=True
        )
        self.wifi = AttributeValue.objects.create(
            attribute_type=self.kind, value="Wi-Fi"
        )
        self.pool = AttributeValue.objects.create(
            attribute_type=self.kind, value="Бассейн"
        )

    def formset(self, values, initial=0, extra=None):
        data = {
            "attributes-TOTAL_FORMS": str(len(values)),
            "attributes-INITIAL_FORMS": str(initial),
        }
        for i, value in enumerate(values):
            data.update(
                {
                    f"attributes-{i}-attribute_type": str(self.kind.pk),
                    f"attributes-{i}-attribute_value": str(value.pk),
                }
            )
        data.update(extra or {})
        return ManagerAttributeFormSet(data, instance=self.product)

    def test_multiple_values_are_saved(self):
        forms = self.formset([self.wifi, self.pool])
        self.assertTrue(forms.is_valid(), (forms.errors, forms.non_form_errors()))
        forms.save()
        self.assertEqual(self.product.attributes.count(), 2)

    def test_repeated_value_is_rejected_before_save(self):
        forms = self.formset([self.wifi, self.wifi])
        self.assertFalse(forms.is_valid())
        self.assertEqual(self.product.attributes.count(), 0)

    def test_database_rejects_repeated_nonempty_value(self):
        ProductAttribute.objects.create(
            product=self.product, attribute_type=self.kind, attribute_value=self.wifi
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductAttribute.objects.create(
                product=self.product,
                attribute_type=self.kind,
                attribute_value=self.wifi,
            )

    def test_single_type_rejects_two_different_values(self):
        self.kind.allow_multiple = False
        self.kind.save()
        self.assertFalse(self.formset([self.wifi, self.pool]).is_valid())

    def test_omitted_existing_row_still_counts(self):
        self.kind.allow_multiple = False
        self.kind.save()
        ProductAttribute.objects.create(
            product=self.product, attribute_type=self.kind, attribute_value=self.wifi
        )
        self.assertFalse(self.formset([self.pool]).is_valid())

    def test_deletion_allows_replacement_of_single_value(self):
        self.kind.allow_multiple = False
        self.kind.save()
        record = ProductAttribute.objects.create(
            product=self.product, attribute_type=self.kind, attribute_value=self.wifi
        )
        forms = self.formset(
            [self.wifi, self.pool],
            initial=1,
            extra={"attributes-0-id": str(record.pk), "attributes-0-DELETE": "on"},
        )
        self.assertTrue(forms.is_valid(), (forms.errors, forms.non_form_errors()))
        forms.save()
        self.assertEqual(self.product.attributes.get().attribute_value, self.pool)

    def test_multiple_flag_cannot_be_disabled_while_values_exist(self):
        for value in [self.wifi, self.pool]:
            ProductAttribute.objects.create(
                product=self.product, attribute_type=self.kind, attribute_value=value
            )
        self.kind.allow_multiple = False
        with self.assertRaises(ValidationError):
            self.kind.full_clean()

    def test_multiple_flag_requires_choice_type(self):
        self.kind.data_type = "number"
        with self.assertRaises(ValidationError):
            self.kind.full_clean()

    def test_value_from_another_type_is_rejected(self):
        other = AttributeType.objects.create(
            name="Другой", slug="other", data_type="choice"
        )
        value = AttributeValue.objects.create(attribute_type=other, value="Другое")
        self.assertFalse(self.formset([value]).is_valid())

"""Проверка выбора флажками, прав и атомарного сохранения редакторов."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.products.models import (
    AttributeType,
    AttributeValue,
    Product,
    ProductAttribute,
)
from apps.products.multiple_attribute_forms import build_multiple_form
from apps.users.constants import ROLE_MANAGER


class MultipleCheckboxTests(TestCase):
    """Два интерфейса должны сохранять одинаковые связи без потери строк."""

    def setUp(self):
        self.product = Product.objects.create(title="Дом", slug="house", price=100)
        self.kind = AttributeType.objects.create(
            name="Удобства", slug="amenities", data_type="choice", allow_multiple=True
        )
        self.wifi = AttributeValue.objects.create(
            attribute_type=self.kind, value="Wi-Fi"
        )
        self.pool = AttributeValue.objects.create(
            attribute_type=self.kind, value="Бассейн"
        )
        self.row = ProductAttribute.objects.create(
            product=self.product,
            attribute_type=self.kind,
            attribute_value=self.wifi,
            sort_order=17,
        )
        self.field = f"multiple_attribute_{self.kind.pk}"

    def manager(self):
        user = get_user_model().objects.create_user("manager", password="test-password")
        user.profile.role = ROLE_MANAGER
        user.profile.save()
        self.client.force_login(user)
        return reverse("catalog:product_attributes", args=[self.product.pk])

    def data(self, values):
        return {
            "attributes-TOTAL_FORMS": "0",
            "attributes-INITIAL_FORMS": "0",
            "multiple-" + self.field: [str(v.pk) for v in values],
        }

    def test_selected_rows_keep_identity_and_order(self):
        form = build_multiple_form()(
            {self.field: [self.wifi.pk, self.pool.pk]}, product=self.product
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save_multiple(self.product)
        self.row.refresh_from_db()
        self.assertEqual(self.row.sort_order, 17)
        self.assertEqual(self.product.attributes.count(), 2)

    def test_unchecking_removes_only_link_and_preserves_single_type(self):
        kind = AttributeType.objects.create(
            name="Комнаты", slug="rooms", data_type="number"
        )
        value = AttributeValue.objects.create(attribute_type=kind, value="2")
        single = ProductAttribute.objects.create(
            product=self.product, attribute_type=kind, attribute_value=value
        )
        form = build_multiple_form()({}, product=self.product)
        self.assertTrue(form.is_valid())
        form.save_multiple(self.product)
        self.assertFalse(ProductAttribute.objects.filter(pk=self.row.pk).exists())
        self.assertTrue(ProductAttribute.objects.filter(pk=single.pk).exists())
        self.assertTrue(AttributeValue.objects.filter(pk=self.wifi.pk).exists())

    def test_manager_shows_checkboxes_and_saves_selection(self):
        url = self.manager()
        response = self.client.get(url)
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, "multiple-" + self.field)
        formset = response.context["formset"]
        self.assertEqual(formset.initial_form_count(), 0)
        self.assertFalse(
            formset.empty_form.fields["attribute_type"]
            .queryset.filter(pk=self.kind.pk)
            .exists()
        )
        self.assertEqual(
            self.client.post(url, self.data([self.wifi, self.pool])).status_code, 302
        )
        self.assertEqual(self.product.attributes.count(), 2)

    def test_invalid_choice_cannot_delete_existing_values(self):
        url = self.manager()
        other = AttributeType.objects.create(
            name="Другой", slug="other", data_type="choice"
        )
        value = AttributeValue.objects.create(
            attribute_type=other, value="Чужое значение"
        )
        self.assertEqual(self.client.post(url, self.data([value])).status_code, 200)
        self.assertTrue(ProductAttribute.objects.filter(pk=self.row.pk).exists())

    def test_invalid_single_form_cannot_change_checkboxes(self):
        url = self.manager()
        data = self.data([self.pool])
        data.update(
            {
                "attributes-TOTAL_FORMS": "1",
                "attributes-0-attribute_type": "999999",
                "attributes-0-free_value": "1",
            }
        )
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertTrue(ProductAttribute.objects.filter(pk=self.row.pk).exists())
        self.assertFalse(
            self.product.attributes.filter(attribute_value=self.pool).exists()
        )

    def test_admin_shows_and_saves_checkboxes(self):
        user = get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "test-password"
        )
        self.client.force_login(user)
        url = reverse("admin:products_product_change", args=[self.product.pk])
        response = self.client.get(url)
        self.assertContains(response, self.field)
        data = {
            "title": self.product.title,
            "slug": self.product.slug,
            "price": "100",
            "currency": "RUB",
            "availability_status": self.product.availability_status,
            "is_active": "on",
            self.field: [self.wifi.pk, self.pool.pk],
            "_save": "Сохранить",
        }
        for inline in response.context["inline_admin_formsets"]:
            fs = inline.formset
            data[fs.prefix + "-TOTAL_FORMS"] = str(fs.total_form_count())
            data[fs.prefix + "-INITIAL_FORMS"] = str(fs.initial_form_count())
            for i in range(fs.total_form_count()):
                data[f"{fs.prefix}-{i}-sort_order"] = "0"
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, 302, str(getattr(response, "context", None))
        )
        self.assertEqual(self.product.attributes.count(), 2)

    def test_admin_without_attribute_permissions_cannot_edit_checkboxes(self):
        user = get_user_model().objects.create_user(
            "staff", password="test-password", is_staff=True
        )
        user.user_permissions.add(
            Permission.objects.get(
                codename="change_product", content_type__app_label="products"
            )
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("admin:products_product_change", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.field)

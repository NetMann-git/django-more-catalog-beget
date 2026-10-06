"""Контакты жилья, тарифы и сохранность записей при расширении Product."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from apps.products.admin import ProductAdmin
from apps.products.forms import ProductForm
from apps.products.models import Location, Product
from apps.users.constants import ROLE_MANAGER

NEW_FIELDS = (
    "address", "contact_name", "contact_phone", "additional_contact_name",
    "additional_contact_phone", "contact_email", "price_description", "internal_notes",
)


class HousingContactTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title="Дом", slug="house", price=1500)
        self.location = Location.objects.create(name="Адлер", slug="adler")
        self.user = get_user_model().objects.create_user("contacts-manager", password="test")
        self.user.profile.role = ROLE_MANAGER
        self.user.profile.save()

    def data(self):
        """Поля основной формы вместе с новыми данными жилья."""
        return {
            "title": "Дом", "slug": "house", "price": "1500", "currency": "RUB",
            "availability_status": "in_stock", "is_active": "on",
            "location": str(self.location.pk), "address": "Адлер, ул. Морская, 1",
            "contact_name": "Хозяин", "contact_phone": "+7 (900) 000-00-00, +7 900 111-11-11",
            "additional_contact_name": "Администратор", "additional_contact_phone": "+7 900 222-22-22",
            "contact_email": "owner@example.com",
            "price_description": "<table><tr><td>Июль: 3000 руб.</td></tr></table>",
            "internal_notes": "ВНУТРЕННЯЯ-ЗАМЕТКА-НЕ-ПУБЛИКОВАТЬ",
        }

    def test_manager_saves_and_clears_optional_fields(self):
        self.client.force_login(self.user)
        url = reverse("catalog:product_edit", args=[self.product.pk])
        data = self.data()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.location_id, self.location.pk)
        for name in NEW_FIELDS:
            self.assertEqual(getattr(self.product, name), data[name])
        self.assertContains(self.client.get(url), "Описание тарифов")
        self.assertContains(self.client.get(url), "Внутренние заметки")
        for name in NEW_FIELDS:
            data[name] = ""
        data["location"] = ""
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.product.refresh_from_db()
        self.assertIsNone(self.product.location_id)
        self.assertTrue(all(getattr(self.product, name) == "" for name in NEW_FIELDS))

    def test_email_validation_prevents_partial_save(self):
        data = self.data()
        data["contact_email"] = "не email"
        form = ProductForm(data, instance=self.product)
        self.assertFalse(form.is_valid())
        self.assertIn("contact_email", form.errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.address, "")

    def test_old_record_can_be_saved_without_new_fields(self):
        data = self.data()
        for name in NEW_FIELDS + ("location",):
            data.pop(name)
        form = ProductForm(data, instance=self.product)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertTrue(all(getattr(self.product, name) == "" for name in NEW_FIELDS))

    def test_notes_not_in_public_pages_and_customer_cannot_edit(self):
        self.product.internal_notes = self.data()["internal_notes"]
        self.product.save()
        for url in [self.product.get_absolute_url(), reverse("catalog:catalog")]:
            self.assertNotContains(self.client.get(url), self.product.internal_notes)
        customer = get_user_model().objects.create_user("customer-contacts", password="test")
        self.client.force_login(customer)
        response = self.client.post(reverse("catalog:product_edit", args=[self.product.pk]), self.data())
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.address, "")

    def test_admin_contains_all_fields(self):
        model_admin = ProductAdmin(Product, admin.site)
        fields = {name for _, options in model_admin.fieldsets for name in options["fields"]}
        self.assertTrue(set(NEW_FIELDS).issubset(fields))
        self.assertIn("address", model_admin.search_fields)


class HousingContactMigrationTests(TransactionTestCase):
    def test_migration_preserves_existing_product_and_relations(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        before = [("products", "0008_alter_brand_options_alter_brand_logo_and_more")]
        after = [("products", "0009_product_additional_contact_name_and_more")]
        try:
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps
            kind = apps.get_model("products", "Brand").objects.create(name="Гостиницы", slug="hotels")
            location = apps.get_model("products", "Location").objects.create(name="Адлер", slug="adler")
            product = apps.get_model("products", "Product").objects.create(title="До миграции", slug="before", price=1234, brand_id=kind.pk, location_id=location.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            migrated = executor.loader.project_state(after).apps.get_model("products", "Product").objects.get(pk=product.pk)
            self.assertEqual(migrated.title, "До миграции")
            self.assertEqual(migrated.price, 1234)
            self.assertEqual(migrated.brand_id, kind.pk)
            self.assertEqual(migrated.location_id, location.pk)
            self.assertTrue(all(getattr(migrated, name) == "" for name in NEW_FIELDS))
        finally:
            MigrationExecutor(connection).migrate(leaves)

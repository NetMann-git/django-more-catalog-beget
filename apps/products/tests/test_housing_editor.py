"""Полный редактор разделов жилья и совместимость прежних записей."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from apps.products.admin import ProductAdmin
from apps.products.forms import ProductForm
from apps.products.housing_editor_layout import HOUSING_EDITOR_SECTIONS
from apps.products.models import Product
from apps.users.constants import ROLE_MANAGER

SECTION_FIELDS = (
    "subtitle", "district_text", "location_description", "rooms_description",
    "meals_description", "beach_description", "beach_distance_description",
    "special_conditions", "additional_services", "booking_conditions",
    "checkin_checkout_description", "included_services", "paid_services", "extra_beds_description",
)


class HousingEditorTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("full-editor", password="test")
        user.profile.role = ROLE_MANAGER
        user.profile.save()
        self.client.force_login(user)
        self.product = Product.objects.create(title="Дом", slug="house")
        self.url = reverse("catalog:product_edit", args=[self.product.pk])

    def data(self):
        """Содержимое всех новых разделов вместе с полями исходной формы."""
        data = {"title": "Дом", "slug": "house", "price": "", "currency": "RUB", "availability_status": "in_stock", "is_active": "on"}
        data.update({name: f"Описание раздела {name}" for name in SECTION_FIELDS})
        data["rooms_description"] = "<p>Комнаты на 2–4 человека</p>"
        return data

    def test_manager_saves_all_sections_and_can_clear_them(self):
        data = self.data()
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.product.refresh_from_db()
        for name in SECTION_FIELDS:
            self.assertEqual(getattr(self.product, name), data[name])
        self.assertIsNone(self.product.price)
        for name in SECTION_FIELDS:
            data[name] = ""
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.product.refresh_from_db()
        self.assertTrue(all(getattr(self.product, name) == "" for name in SECTION_FIELDS))

    def test_grouping_contains_every_field_once_in_both_interfaces(self):
        form = ProductForm()
        names = [field.name for _, fields in form.editor_sections for field in fields]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(form.fields))
        model_admin = ProductAdmin(Product, admin.site)
        self.assertEqual([(title, options["fields"]) for title, options in model_admin.fieldsets], list(HOUSING_EDITOR_SECTIONS))
        response = self.client.get(self.url)
        self.assertContains(response, 'class="housing-editor__section"', count=len(HOUSING_EDITOR_SECTIONS))
        for title, _ in HOUSING_EDITOR_SECTIONS:
            self.assertContains(response, f"<legend>{title}</legend>", html=True)
        self.assertContains(response, reverse("catalog:gallery_add", args=[self.product.pk]))
        self.assertContains(response, reverse("catalog:product_attributes", args=[self.product.pk]))

    def test_invalid_form_preserves_submitted_sections_without_partial_save(self):
        data = self.data()
        data["contact_email"] = "invalid-email"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Описание раздела booking_conditions")
        self.assertContains(response, "&lt;p&gt;Комнаты на 2–4 человека&lt;/p&gt;")
        self.product.refresh_from_db()
        self.assertEqual(self.product.booking_conditions, "")

    def test_old_form_remains_valid_and_customer_cannot_edit(self):
        data = self.data()
        for name in SECTION_FIELDS:
            data.pop(name)
        form = ProductForm(data, instance=self.product)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        customer = get_user_model().objects.create_user("full-editor-customer", password="test")
        self.client.force_login(customer)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rooms_description, "")


class HousingEditorMigrationTests(TransactionTestCase):
    def test_preserves_price_contacts_and_notes(self):
        before = [("products", "0010_alter_product_price")]
        after = [("products", "0011_product_additional_services_and_more")]
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(before)
            model = executor.loader.project_state(before).apps.get_model("products", "Product")
            old = model.objects.create(title="До миграции", slug="before-editor", price=None, contact_phone="+7 900 123", internal_notes="Заметка")
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new = executor.loader.project_state(after).apps.get_model("products", "Product").objects.get(pk=old.pk)
            self.assertIsNone(new.price)
            self.assertEqual(new.contact_phone, old.contact_phone)
            self.assertEqual(new.internal_notes, old.internal_notes)
            self.assertTrue(all(getattr(new, name) == "" for name in SECTION_FIELDS))
        finally:
            MigrationExecutor(connection).migrate(leaves)

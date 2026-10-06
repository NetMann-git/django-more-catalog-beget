"""Совместимость существующего Brand со справочником типов жилья."""
from io import StringIO
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from apps.products.admin import BrandAdmin
from apps.products.forms import BrandForm, ProductForm
from apps.products.models import Brand, Product
from apps.users.constants import ROLE_MANAGER


class HousingTypeTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("housing-manager", password="test")
        user.profile.role = ROLE_MANAGER
        user.profile.save()
        self.client.force_login(user)

    def test_existing_data_and_relationships_survive_edit(self):
        brand = Brand.objects.create(name="Старый бренд", slug="old-brand", country="Китай")
        product = Product.objects.create(title="Дом", slug="house", price=100, brand=brand)
        response = self.client.post(reverse("catalog:brand_edit", args=[brand.pk]), {
            "name": "Гостевой дом", "slug": "old-brand", "sort_order": 5,
            "description": "Описание жилья", "country": "Подмена",
        })
        self.assertEqual(response.status_code, 302)
        brand.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(brand.name, "Гостевой дом")
        self.assertEqual(brand.country, "Китай")
        self.assertEqual(product.brand_id, brand.pk)
        self.assertEqual(brand.slug, "old-brand")

    def test_form_admin_and_manager_labels(self):
        self.assertNotIn("country", BrandForm().fields)
        self.assertEqual(ProductForm().fields["brand"].label, "Тип жилья")
        model_admin = BrandAdmin(Brand, admin.site)
        self.assertNotIn("country", model_admin.list_display)
        self.assertNotIn("country", model_admin.search_fields)
        response = self.client.get(reverse("catalog:brand_list_manage"))
        self.assertContains(response, "Управление типами жилья")
        self.assertNotContains(response, "Поиск по названию или стране")
        dashboard = self.client.get(reverse("users:manager_dashboard"))
        self.assertContains(dashboard, "Типы жилья")

    def test_public_filter_and_type_page(self):
        brand = Brand.objects.create(name="Гостиницы", slug="hotels", country="Скрытая страна")
        Product.objects.create(title="Дом", slug="house", price=100, brand=brand)
        self.assertContains(self.client.get(reverse("catalog:catalog")), "Тип жилья")
        response = self.client.get(brand.get_absolute_url())
        self.assertContains(response, "Жильё этого типа")
        self.assertNotContains(response, "Скрытая страна")

    def test_seed_repeat_preserves_existing_records(self):
        old = Brand.objects.create(name="Старый бренд", slug="old")
        existing = Brand.objects.create(name="Квартиры", slug="custom-apartments", description="Сохранить", sort_order=99)
        for _ in range(2):
            call_command("seed_housing_types", stdout=StringIO())
        self.assertEqual(Brand.objects.count(), 5)
        existing.refresh_from_db()
        self.assertEqual(existing.slug, "custom-apartments")
        self.assertEqual(existing.description, "Сохранить")
        self.assertEqual(existing.sort_order, 99)
        self.assertTrue(Brand.objects.filter(pk=old.pk).exists())

    def test_seed_conflict_rolls_back_all_created_records(self):
        Brand.objects.create(name="Другая запись", slug="gostinitsy")
        with self.assertRaises(CommandError):
            call_command("seed_housing_types", stdout=StringIO())
        self.assertEqual(Brand.objects.count(), 1)

"""Неизвестная цена, нулевая цена и безопасная миграция."""
from decimal import Decimal
from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.template.loader import render_to_string
from django.urls import reverse
from apps.products.admin import ProductAdmin
from apps.products.filters import CatalogFilter
from apps.products.forms import ProductForm
from apps.products.models import Product
from apps.products.templatetags.price_format import product_price
from apps.search.services import SearchService


class NullablePriceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.unknown = Product.objects.create(title="Цена неизвестна", slug="unknown")
        self.zero = Product.objects.create(title="Нулевая цена", slug="zero", price=0)
        self.paid = Product.objects.create(title="Есть цена", slug="paid", price=1500)

    def test_form_accepts_empty_price_and_zero(self):
        data = {"title": "Дом", "slug": "new-house", "price": "", "currency": "RUB", "availability_status": "in_stock"}
        form = ProductForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertIsNone(product.price)
        data["slug"] = "zero-house"
        data["price"] = "0"
        form = ProductForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().price, Decimal("0"))

    def test_labels_admin_and_currency(self):
        self.assertEqual(product_price(self.unknown), "Цена по запросу")
        self.assertEqual(product_price(self.zero), "0 ₽")
        self.paid.currency = "USD"
        self.assertEqual(product_price(self.paid), "1\u00a0500 USD")
        self.assertEqual(ProductAdmin(Product, admin.site).formatted_price(self.unknown), "Цена по запросу")

    def test_cards_omit_offer_when_price_unknown(self):
        card = render_to_string("products/_product_card.html", {"product": self.unknown})
        self.assertIn("Цена по запросу", card)
        self.assertNotIn('itemprop="offers"', card)
        self.assertNotIn('itemprop="price"', card)
        zero = render_to_string("products/_product_card.html", {"product": self.zero})
        self.assertIn('itemprop="price"', zero)
        self.assertIn("0 ₽", zero)
        self.assertContains(self.client.get(self.unknown.get_absolute_url()), "Цена по запросу")
        self.assertContains(self.client.get(reverse("catalog:catalog")), "Цена по запросу")

    def test_sort_nulls_last_and_bounds_exclude_unknown(self):
        queryset = Product.objects.all()
        self.assertEqual(list(CatalogFilter({"sort": "price_asc"}).apply(queryset).values_list("pk", flat=True)), [self.zero.pk, self.paid.pk, self.unknown.pk])
        self.assertEqual(list(CatalogFilter({"sort": "price_desc"}).apply(queryset).values_list("pk", flat=True)), [self.paid.pk, self.zero.pk, self.unknown.pk])
        for bound in [{"price_min": "0"}, {"price_max": "2000"}]:
            self.assertNotIn(self.unknown.pk, CatalogFilter(bound).apply(queryset).values_list("pk", flat=True))

    def test_search_returns_null_for_unknown_and_number_string_for_zero(self):
        unknown = next(item for item in SearchService.suggest("неизвестна") if item["type"] == "product")
        zero = next(item for item in SearchService.suggest("Нулевая") if item["type"] == "product")
        self.assertIsNone(unknown["price"])
        self.assertEqual(Decimal(zero["price"]), 0)

    def test_other_templates_display_unknown_price(self):
        for template, context in [
            ("products/manage_list.html", {"products": [self.unknown]}),
            ("products/comparison.html", {"products": [self.unknown]}),
            ("appointments/appointment_form.html", {"product": self.unknown}),
            ("appointments/_appointment_form_ajax.html", {"product": self.unknown}),
        ]:
            with self.subTest(template=template):
                self.assertIn("Цена по запросу", render_to_string(template, context))


class NullablePriceMigrationTests(TransactionTestCase):
    def test_preserves_existing_prices_and_blocks_unsafe_reverse(self):
        before = [("products", "0009_product_additional_contact_name_and_more")]
        after = [("products", "0010_alter_product_price")]
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(before)
            model = executor.loader.project_state(before).apps.get_model("products", "Product")
            old = model.objects.create(title="Старая цена", slug="old-price", price=1234)
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            model = executor.loader.project_state(after).apps.get_model("products", "Product")
            self.assertEqual(model.objects.get(pk=old.pk).price, 1234)
            unknown = model.objects.create(title="Без цены", slug="without-price", price=None)
            with self.assertRaisesMessage(RuntimeError, "Откат остановлен"):
                MigrationExecutor(connection).migrate(before)
            self.assertIsNone(model.objects.get(pk=unknown.pk).price)
            model.objects.filter(pk=unknown.pk).delete()
            MigrationExecutor(connection).migrate(before)
        finally:
            MigrationExecutor(connection).migrate(leaves)

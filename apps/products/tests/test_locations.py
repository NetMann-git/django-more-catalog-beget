"""Проверки географии и совместимости с существующим каталогом."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from apps.products.models import (
    AttributeType,
    AttributeValue,
    Location,
    Product,
    ProductAttribute,
)


class LocationTests(TestCase):
    """Справочник не должен нарушать связи текущих объектов."""

    def test_product_without_location_remains_valid(self):
        product = Product(title="Существующий объект", slug="existing", price=1000)
        product.full_clean()
        product.save()
        self.assertIsNone(product.location_id)

    def test_location_in_use_cannot_be_deleted(self):
        location = Location.objects.create(name="Адлер", slug="adler")
        Product.objects.create(
            title="Объект", slug="object", price=1000, location=location
        )
        with self.assertRaises(ProtectedError):
            location.delete()

    def test_parent_cannot_be_own_descendant(self):
        parent = Location.objects.create(name="Сочи", slug="sochi")
        child = Location.objects.create(name="Адлер", slug="adler", parent=parent)
        parent.parent = child
        with self.assertRaises(ValidationError):
            parent.full_clean()

    def test_admin_forms_support_location_selection(self):
        user = get_user_model().objects.create_superuser(
            "location_admin", "admin@example.com", "test-password"
        )
        self.client.force_login(user)
        for name in [
            "products_location_add",
            "products_location_changelist",
            "products_product_add",
        ]:
            self.assertEqual(self.client.get(reverse("admin:" + name)).status_code, 200)

    def test_existing_attribute_uniqueness_is_preserved(self):
        """Множественные удобства требуют отдельного согласованного изменения."""
        product = Product.objects.create(title="Объект", slug="object", price=1000)
        kind = AttributeType.objects.create(
            name="Удобства", slug="amenities", data_type="choice"
        )
        wifi = AttributeValue.objects.create(attribute_type=kind, value="Wi-Fi")
        pool = AttributeValue.objects.create(attribute_type=kind, value="Бассейн")
        ProductAttribute.objects.create(
            product=product, attribute_type=kind, attribute_value=wifi
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductAttribute.objects.create(
                product=product, attribute_type=kind, attribute_value=pool
            )


class LocationMigrationTests(TransactionTestCase):
    """Добавление связи сохраняет данные уже существующего Product."""

    def test_existing_product_survives_forward_migration(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("products", "0004_brand_sort_order")])
            apps = executor.loader.project_state(
                [("products", "0004_brand_sort_order")]
            ).apps
            old_product = apps.get_model("products", "Product").objects.create(
                title="До миграции", slug="before-migration", price=1234
            )
            executor = MigrationExecutor(connection)
            executor.migrate([("products", "0005_location_product_location")])
            apps = executor.loader.project_state(
                [("products", "0005_location_product_location")]
            ).apps
            product = apps.get_model("products", "Product").objects.get(
                pk=old_product.pk
            )
            self.assertEqual(product.title, "До миграции")
            self.assertEqual(product.price, 1234)
            self.assertIsNone(product.location_id)
        finally:
            MigrationExecutor(connection).migrate(leaves)

"""Загрузка и отображение иконок в интерфейсах менеджера и админки."""
import tempfile
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib import admin
from apps.users.constants import ROLE_MANAGER
from apps.products.admin import AttributeTypeAdmin
from apps.products.models import AttributeType, AttributeValue, Product
from apps.products.multiple_attribute_forms import build_multiple_form
from apps.products.product_attribute_forms import ProductAttributeForm
from apps.products.tests.test_attribute_icons import uploaded_icon


class ManagerAttributeIconTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        user = get_user_model().objects.create_user("icon-manager", password="test")
        user.profile.role = ROLE_MANAGER
        user.profile.save()
        self.client.force_login(user)

    def test_manager_uploads_type_and_value_and_clears_icon(self):
        self.client.post(reverse("catalog:attribute_type_create"), {
            "name": "Удобства", "slug": "amenities", "data_type": "choice",
            "icon": uploaded_icon(),
        })
        kind = AttributeType.objects.get(slug="amenities")
        self.assertTrue(kind.icon)
        url = reverse("catalog:attribute_type_edit", args=[kind.pk])
        response = self.client.get(url)
        self.assertContains(response, 'enctype="multipart/form-data"', count=2)
        self.assertContains(response, kind.icon.url)
        self.client.post(reverse("catalog:attribute_value_create", args=[kind.pk]), {
            "value": "Бассейн", "sort_order": 0, "icon": uploaded_icon("pool.webp", image_format="WEBP"),
        })
        value = AttributeValue.objects.get(attribute_type=kind)
        self.assertTrue(value.icon)
        value_url = reverse("catalog:attribute_value_edit", args=[kind.pk, value.pk])
        self.assertContains(self.client.get(value_url), value.icon.url)
        self.client.post(value_url, {"value": "Бассейн", "sort_order": 0, "icon-clear": "on"})
        value.refresh_from_db()
        self.assertFalse(value.icon)
        self.client.post(url, {"name": kind.name, "data_type": "choice", "icon-clear": "on"})
        kind.refresh_from_db()
        self.assertFalse(kind.icon)

    def test_invalid_upload_keeps_original(self):
        kind = AttributeType.objects.create(name="Тип", slug="type", data_type="choice", icon=uploaded_icon())
        original = kind.icon.name
        response = self.client.post(reverse("catalog:attribute_type_edit", args=[kind.pk]), {
            "name": kind.name, "data_type": "choice", "icon": uploaded_icon(size=(257, 32)),
        })
        self.assertContains(response, "256 × 256")
        kind.refresh_from_db()
        self.assertEqual(kind.icon.name, original)

    def test_editor_displays_icons_and_escapes_labels(self):
        kind = AttributeType.objects.create(name="<script>тип</script>", slug="amenities", data_type="choice", allow_multiple=True, icon=uploaded_icon())
        value = AttributeValue.objects.create(attribute_type=kind, value="<script>значение</script>", icon=uploaded_icon("value.png"))
        product = Product.objects.create(title="Дом", slug="house", price=100)
        response = self.client.get(reverse("catalog:product_attributes", args=[product.pk]))
        self.assertContains(response, kind.icon.url)
        self.assertContains(response, value.icon.url)
        self.assertNotContains(response, "<script>тип</script>")
        self.assertContains(response, "&lt;script&gt;значение&lt;/script&gt;")
        value.icon = ""
        value.save()
        rendered = str(build_multiple_form()(product=product)[f"multiple_attribute_{kind.pk}"])
        self.assertIn(kind.icon.url, rendered)
        single = ProductAttributeForm()
        self.assertIn('data-icon=', str(single["attribute_type"]))
        self.assertIn(kind.icon.url, str(single["attribute_value"]))

    def test_admin_links_name(self):
        model_admin = AttributeTypeAdmin(AttributeType, admin.site)
        self.assertEqual(model_admin.list_display_links, ("name",))

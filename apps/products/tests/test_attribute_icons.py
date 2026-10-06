"""Проверки файлов иконок и сохранения ссылок справочника."""
import tempfile
from io import BytesIO
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from apps.products.models import AttributeType, AttributeValue
from apps.products.icon_validators import validate_attribute_icon


def uploaded_icon(name="icon.png", size=(32, 32), image_format="PNG"):
    """Создать настоящее изображение для проверки загрузки."""
    buffer = BytesIO()
    Image.new("RGBA", size, (0, 0, 0, 0)).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue())


class AttributeIconTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.kind = AttributeType.objects.create(name="Удобства", slug="amenities", data_type="choice")
        self.value = AttributeValue.objects.create(attribute_type=self.kind, value="Бассейн")

    def test_optional_and_fallback(self):
        self.kind.full_clean()
        self.value.full_clean()
        self.assertFalse(self.value.effective_icon)
        self.kind.icon = uploaded_icon()
        self.kind.full_clean()
        self.kind.save()
        self.assertEqual(self.value.effective_icon.name, self.kind.icon.name)
        self.value.icon = uploaded_icon("pool.webp", image_format="WEBP")
        self.value.full_clean()
        self.value.save()
        self.assertEqual(self.value.effective_icon.name, self.value.icon.name)

    def test_validator_rejects_invalid_files_and_restores_cursor(self):
        valid = uploaded_icon()
        valid.seek(3)
        validate_attribute_icon(valid)
        self.assertEqual(valid.tell(), 3)
        invalid = [uploaded_icon(size=(257, 32)), uploaded_icon("icon.svg"),
                   SimpleUploadedFile("fake.png", b"not an image"),
                   SimpleUploadedFile("big.png", b"x" * (256 * 1024 + 1)),
                   uploaded_icon("fake.png", image_format="GIF")]
        for value in invalid:
            with self.subTest(name=value.name, size=value.size):
                with self.assertRaises(ValidationError):
                    validate_attribute_icon(value)

    def test_replacement_and_shared_reference_cleanup(self):
        self.kind.icon = uploaded_icon()
        self.kind.save()
        old_name = self.kind.icon.name
        storage = self.kind.icon.storage
        self.value.icon = old_name
        self.value.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.kind.icon = uploaded_icon("replacement.png")
            self.kind.save()
        self.assertTrue(storage.exists(old_name))
        with self.captureOnCommitCallbacks(execute=True):
            self.value.delete()
        self.assertFalse(storage.exists(old_name))
        new_name = self.kind.icon.name
        with self.captureOnCommitCallbacks(execute=True):
            self.kind.icon = ""
            self.kind.save()
        self.assertFalse(storage.exists(new_name))

    def test_cascade_deletion_cleans_icons(self):
        self.kind.icon = uploaded_icon()
        self.kind.save()
        self.value.icon = uploaded_icon("pool.png")
        self.value.save()
        names = [self.kind.icon.name, self.value.icon.name]
        storage = self.kind.icon.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.kind.delete()
        self.assertTrue(all(not storage.exists(name) for name in names))

    def test_animation_rejected(self):
        buffer = BytesIO()
        Image.new("RGBA", (32, 32), "red").save(
            buffer, format="PNG", save_all=True,
            append_images=[Image.new("RGBA", (32, 32), "blue")], duration=100,
        )
        with self.assertRaises(ValidationError):
            validate_attribute_icon(SimpleUploadedFile("animated.png", buffer.getvalue()))

    def test_admin_upload_and_inline_preview(self):
        from django.contrib import admin
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory
        from apps.products.admin import AttributeTypeAdmin, AttributeValueInline
        request = RequestFactory().get("/admin/products/attributetype/")
        request.user = get_user_model().objects.create_superuser("icons-admin", "icons@example.com", "test")
        model_admin = AttributeTypeAdmin(AttributeType, admin.site)
        form_class = model_admin.get_form(request, self.kind)
        form = form_class(
            data={"name": self.kind.name, "slug": self.kind.slug, "data_type": "choice"},
            files={"icon": uploaded_icon()}, instance=self.kind,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIn(self.kind.icon.url, str(model_admin.icon_preview(self.kind)))
        inline = AttributeValueInline(AttributeType, admin.site)
        self.assertIn("icon", inline.fields)
        self.assertIn("icon_preview", inline.readonly_fields)
        self.assertEqual(inline.icon_preview(self.value), "—")

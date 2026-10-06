"""Проверка загружаемых иконок справочника."""
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError


def validate_attribute_icon(value):
    """Разрешить небольшие статические PNG/WebP с проверкой содержимого."""
    if not value:
        return
    if value.size > 256 * 1024:
        raise ValidationError("Размер иконки не должен превышать 256 КБ.")
    if Path(value.name).suffix.lower() not in {".png", ".webp"}:
        raise ValidationError("Загрузите иконку PNG или WebP.")
    position = value.tell()
    try:
        value.seek(0)
        with Image.open(value) as image:
            if image.format not in {"PNG", "WEBP"}:
                raise ValidationError("Содержимое файла должно быть PNG или WebP.")
            if image.width > 256 or image.height > 256:
                raise ValidationError("Размеры иконки не должны превышать 256 × 256 пикселей.")
            if getattr(image, "is_animated", False):
                raise ValidationError("Загрузите статическую иконку без анимации.")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValidationError("Не удалось прочитать изображение.") from error
    finally:
        value.seek(position)

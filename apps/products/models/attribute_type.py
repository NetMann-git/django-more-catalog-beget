# apps/products/models/attribute_type.py
from django.core.exceptions import ValidationError
from apps.products.icon_validators import validate_attribute_icon
from django.db import models
from django.db.models import Count


class AttributeType(models.Model):
    """
    Тип характеристики (например, "Силуэт", "Коллекция", "Цвет").
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="Slug")

    DATA_TYPES = (
        ("string", "Строка"),
        ("number", "Число"),
        ("choice", "Выбор из списка"),
    )
    data_type = models.CharField(
        max_length=20, choices=DATA_TYPES, default="string", verbose_name="Тип данных"
    )

    allow_multiple = models.BooleanField(
        "Разрешить несколько значений",
        default=False,
        help_text="Для удобств включите этот признак и выберите тип данных «Выбор из списка».",
    )

    def clean(self):
        """Не отключать множественный выбор, пока в объектах есть несколько значений."""
        super().clean()
        if self.allow_multiple and self.data_type != "choice":
            raise ValidationError(
                {"allow_multiple": "Множественный выбор доступен для списка."}
            )
        if self.pk and not self.allow_multiple:
            duplicates = (
                self.product_attributes.values("product_id")
                .annotate(amount=Count("pk"))
                .filter(amount__gt=1)
            )
            if duplicates.exists():
                raise ValidationError(
                    {
                        "allow_multiple": "Сначала оставьте одно значение этого типа у каждого объекта."
                    }
                )

    icon = models.ImageField(
        "Иконка", upload_to="attributes/types/", blank=True,
        validators=[validate_attribute_icon],
        help_text="Необязательно: статический PNG/WebP до 256 × 256 пикселей и 256 КБ.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Тип характеристики"
        verbose_name_plural = "Типы характеристик"

    def __str__(self):
        return self.name

# apps/products/models/attribute_value.py

from apps.products.icon_validators import validate_attribute_icon
from django.db import models
from .attribute_type import AttributeType


class AttributeValue(models.Model):
    attribute_type = models.ForeignKey(
        AttributeType,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name="Тип характеристики"
    )
    value = models.CharField(
        max_length=255,
        verbose_name="Значение"
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    icon = models.ImageField(
        "Иконка", upload_to="attributes/values/", blank=True,
        validators=[validate_attribute_icon],
        help_text="Необязательно: статический PNG/WebP до 256 × 256 пикселей и 256 КБ.",
    )

    @property
    def effective_icon(self):
        """Использовать иконку значения, затем иконку типа, если она задана."""
        return self.icon or self.attribute_type.icon

    class Meta:
        ordering = ["sort_order", "value"]
        unique_together = ("attribute_type", "value")
        verbose_name = "Значение характеристики"
        verbose_name_plural = "Значения характеристик"

    def __str__(self):
        return self.value
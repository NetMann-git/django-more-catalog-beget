# apps/products/models/product_attribute.py
from django.core.exceptions import ValidationError
from django.db import models
from .product_model import Product
from .attribute_type import AttributeType
from .attribute_value import AttributeValue
from smart_selects.db_fields import ChainedForeignKey


class ProductAttribute(models.Model):
    """
    Значение характеристики для конкретного товара.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="attributes",
        verbose_name="Товар",
    )
    attribute_type = models.ForeignKey(
        AttributeType,
        on_delete=models.PROTECT,
        related_name="product_attributes",
        verbose_name="Тип характеристики",
        null=False,  # временно разрешаем NULL
        blank=False,  # временно разрешаем пустое значение
    )
    attribute_value = ChainedForeignKey(
        AttributeValue,
        chained_field="attribute_type",
        chained_model_field="attribute_type",
        show_all=False,
        auto_choose=True,
        on_delete=models.PROTECT,
        related_name="product_attributes",
        verbose_name="Значение",
        null=True,
        blank=True,
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок",
    )

    def clean(self):
        """Проверить принадлежность значения и одиночные характеристики."""
        super().clean()
        if not self.attribute_type_id:
            return
        if (
            self.attribute_value_id
            and self.attribute_value.attribute_type_id != self.attribute_type_id
        ):
            raise ValidationError(
                {"attribute_value": "Значение относится к другому типу."}
            )
        # В наборе форм проверяется конечное состояние с учётом удаляемых строк.
        if getattr(self, "_validated_in_formset", False):
            return
        if self.product_id and not self.attribute_type.allow_multiple:
            existing = ProductAttribute.objects.filter(
                product_id=self.product_id, attribute_type_id=self.attribute_type_id
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    {
                        "attribute_type": "У этого объекта уже есть значение одиночной характеристики."
                    }
                )

    class Meta:
        ordering = ["sort_order", "attribute_type__name"]
        unique_together = (
            "product",
            "attribute_type",
            "attribute_value",
        )  # Повтор значения запрещён в БД.
        verbose_name = "Характеристика товара"
        verbose_name_plural = "Характеристики товаров"


def __str__(self):
    value = getattr(self.attribute_value, "value", "не указано")
    return f"{self.attribute_type.name}: {value}"

# Множественный выбор характеристик с сохранением текущих значений.

from django.db import migrations, models
from django.db.models import Count


def check_reverse(apps, schema_editor):
    """Не возвращать старое ограничение, если уже сохранены несколько значений."""
    rows = apps.get_model("products", "ProductAttribute").objects.using(
        schema_editor.connection.alias
    )
    if (
        rows.values("product_id", "attribute_type_id")
        .annotate(amount=Count("pk"))
        .filter(amount__gt=1)
        .exists()
    ):
        raise RuntimeError(
            "Откат остановлен: сначала оставьте одно значение каждого типа у объекта."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_location_product_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="attributetype",
            name="allow_multiple",
            field=models.BooleanField(
                default=False,
                help_text="Для удобств включите этот признак и выберите тип данных «Выбор из списка».",
                verbose_name="Разрешить несколько значений",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="productattribute",
            unique_together={("product", "attribute_type", "attribute_value")},
        ),
        migrations.RunPython(migrations.RunPython.noop, check_reverse),
    ]

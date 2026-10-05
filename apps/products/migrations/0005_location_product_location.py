# Добавление справочника локаций и необязательной связи с Product.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_brand_sort_order"),
    ]

    operations = [
        migrations.CreateModel(
            name="Location",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150, verbose_name="Название")),
                (
                    "slug",
                    models.SlugField(
                        max_length=180, unique=True, verbose_name="URL-код"
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="Описание локации"),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="products.location",
                        verbose_name="Родительская локация",
                    ),
                ),
            ],
            options={
                "verbose_name": "Локация",
                "verbose_name_plural": "Локации",
                "ordering": ("name", "pk"),
            },
        ),
        migrations.AddField(
            model_name="product",
            name="location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="products.location",
                verbose_name="Локация",
            ),
        ),
    ]

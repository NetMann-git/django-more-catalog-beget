# Пустая цена означает неизвестную стоимость, а не ноль.

from django.db import migrations, models


def check_reverse(apps, schema_editor):
    """Не возвращать обязательную цену, пока есть записи без стоимости."""
    product = apps.get_model("products", "Product")
    if product.objects.using(schema_editor.connection.alias).filter(price__isnull=True).exists():
        raise RuntimeError(
            "Откат остановлен: есть объекты без цены. Заполните их цены перед откатом."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_product_additional_contact_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Оставьте пустым, если цена неизвестна: будет показано «Цена по запросу».', max_digits=10, null=True, verbose_name='Цена'),
        ),
        migrations.RunPython(migrations.RunPython.noop, check_reverse),
    ]
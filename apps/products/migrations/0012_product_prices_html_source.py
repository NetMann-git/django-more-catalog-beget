from django.db import migrations, models
from django.db.models import F


def archive(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.using(schema_editor.connection.alias).exclude(price_description='').update(price_description_source=F('price_description'))


class Migration(migrations.Migration):
    dependencies = [('products', '0011_product_additional_services_and_more')]
    operations = [
        migrations.AddField(model_name='product', name='price_description_source', field=models.TextField(blank=True, editable=False, verbose_name='Исходный HTML цен', help_text='Архив первого непустого HTML. Не выводится публично.')),
        migrations.AlterField(model_name='product', name='price_description', field=models.TextField(blank=True, verbose_name='Цены', help_text='Сезонные цены, тарифы номеров и условия оплаты. Числовую цену не заменяет.')),
        migrations.RunPython(archive, migrations.RunPython.noop),
    ]

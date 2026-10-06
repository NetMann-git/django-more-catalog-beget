# Переименование справочника в интерфейсе без удаления полей и связей.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_attributetype_icon_attributevalue_icon'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='brand',
            options={'ordering': ['name'], 'verbose_name': 'Тип жилья', 'verbose_name_plural': 'Типы жилья'},
        ),
        migrations.AlterField(
            model_name='brand',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='brands/', verbose_name='Изображение типа жилья'),
        ),
        migrations.AlterField(
            model_name='brand',
            name='meta_title',
            field=models.CharField(blank=True, help_text='Если не заполнено, будет использоваться название типа жилья.', max_length=255, verbose_name='SEO Title'),
        ),
        migrations.AlterField(
            model_name='product',
            name='brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='products.brand', verbose_name='Тип жилья'),
        ),
    ]
# Необязательные иконки существующих справочников характеристик.

import apps.products.icon_validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_attributetype_allow_multiple_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attributetype',
            name='icon',
            field=models.ImageField(blank=True, help_text='Необязательно: статический PNG/WebP до 256 × 256 пикселей и 256 КБ.', upload_to='attributes/types/', validators=[apps.products.icon_validators.validate_attribute_icon], verbose_name='Иконка'),
        ),
        migrations.AddField(
            model_name='attributevalue',
            name='icon',
            field=models.ImageField(blank=True, help_text='Необязательно: статический PNG/WebP до 256 × 256 пикселей и 256 КБ.', upload_to='attributes/values/', validators=[apps.products.icon_validators.validate_attribute_icon], verbose_name='Иконка'),
        ),
    ]
# Необязательные поля жилья; существующие записи и связи сохраняются.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_alter_brand_options_alter_brand_logo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='additional_contact_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Дополнительное контактное лицо'),
        ),
        migrations.AddField(
            model_name='product',
            name='additional_contact_phone',
            field=models.CharField(blank=True, max_length=255, verbose_name='Дополнительный телефон'),
        ),
        migrations.AddField(
            model_name='product',
            name='address',
            field=models.CharField(blank=True, max_length=500, verbose_name='Адрес'),
        ),
        migrations.AddField(
            model_name='product',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Контактный email'),
        ),
        migrations.AddField(
            model_name='product',
            name='contact_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Контактное лицо'),
        ),
        migrations.AddField(
            model_name='product',
            name='contact_phone',
            field=models.CharField(blank=True, help_text='Можно указать несколько номеров; форматирование сохраняется.', max_length=255, verbose_name='Телефон'),
        ),
        migrations.AddField(
            model_name='product',
            name='internal_notes',
            field=models.TextField(blank=True, help_text='Для менеджера и администратора. На публичных страницах не отображается.', verbose_name='Внутренние заметки'),
        ),
        migrations.AddField(
            model_name='product',
            name='price_description',
            field=models.TextField(blank=True, help_text='Сезонные цены, тарифы номеров и условия оплаты. Числовую цену не заменяет.', verbose_name='Описание тарифов'),
        ),
    ]
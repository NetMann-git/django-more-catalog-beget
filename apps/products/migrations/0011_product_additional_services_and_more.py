# Разделы описания и условий жилья; существующие данные сохраняются.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_alter_product_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='additional_services',
            field=models.TextField(blank=True, verbose_name='Дополнительные услуги'),
        ),
        migrations.AddField(
            model_name='product',
            name='beach_description',
            field=models.TextField(blank=True, verbose_name='Пляж'),
        ),
        migrations.AddField(
            model_name='product',
            name='beach_distance_description',
            field=models.TextField(blank=True, verbose_name='Расстояние до пляжа'),
        ),
        migrations.AddField(
            model_name='product',
            name='booking_conditions',
            field=models.TextField(blank=True, verbose_name='Условия бронирования'),
        ),
        migrations.AddField(
            model_name='product',
            name='checkin_checkout_description',
            field=models.TextField(blank=True, verbose_name='Расчётный час'),
        ),
        migrations.AddField(
            model_name='product',
            name='district_text',
            field=models.CharField(blank=True, max_length=255, verbose_name='Район (текст)'),
        ),
        migrations.AddField(
            model_name='product',
            name='extra_beds_description',
            field=models.TextField(blank=True, verbose_name='Дополнительные места'),
        ),
        migrations.AddField(
            model_name='product',
            name='included_services',
            field=models.TextField(blank=True, verbose_name='Входит в стоимость'),
        ),
        migrations.AddField(
            model_name='product',
            name='location_description',
            field=models.TextField(blank=True, verbose_name='Месторасположение'),
        ),
        migrations.AddField(
            model_name='product',
            name='meals_description',
            field=models.TextField(blank=True, verbose_name='Питание'),
        ),
        migrations.AddField(
            model_name='product',
            name='paid_services',
            field=models.TextField(blank=True, verbose_name='За дополнительную плату'),
        ),
        migrations.AddField(
            model_name='product',
            name='rooms_description',
            field=models.TextField(blank=True, verbose_name='Номерной фонд / описание комнат'),
        ),
        migrations.AddField(
            model_name='product',
            name='special_conditions',
            field=models.TextField(blank=True, verbose_name='Особые условия'),
        ),
        migrations.AddField(
            model_name='product',
            name='subtitle',
            field=models.CharField(blank=True, max_length=255, verbose_name='Подзаголовок'),
        ),
    ]
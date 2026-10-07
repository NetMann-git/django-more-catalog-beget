# apps/products/models/product_model.py
from django.db import models
from django.urls import reverse

from .badge import Badge
from .category import Category
from .brand import Brand

from apps.products.constants import (
    CURRENCY_CHOICES,
    AVAILABILITY_CHOICES,
    AVAILABILITY_IN_STOCK,
)

from easy_thumbnails.fields import ThumbnailerImageField

class Product(models.Model):
    """
    Обычная Django-модель товара (без Wagtail).
    """

    # Основная информация
    title = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="URL")

    image = ThumbnailerImageField(
        upload_to="products/",
        blank=True,
        null=True,
        verbose_name="Изображение",
    )

    badges = models.ManyToManyField(
        Badge,
        blank=True,
        related_name="products",
        verbose_name="Бейджи",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_items",
        verbose_name="Категория",
    )
    
    article = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Артикул"
    )
    product_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Тип товара"
    )

    # Необязательная связь сохраняет совместимость существующих записей.
    location = models.ForeignKey(
        "products.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Локация",
    )

    # Поля жилья необязательны: существующие записи остаются совместимыми.
    address = models.CharField("Адрес", max_length=500, blank=True)
    contact_name = models.CharField("Контактное лицо", max_length=255, blank=True)
    contact_phone = models.CharField(
        "Телефон", max_length=255, blank=True,
        help_text="Можно указать несколько номеров; форматирование сохраняется.",
    )
    additional_contact_name = models.CharField(
        "Дополнительное контактное лицо", max_length=255, blank=True,
    )
    additional_contact_phone = models.CharField(
        "Дополнительный телефон", max_length=255, blank=True,
    )
    contact_email = models.EmailField("Контактный email", blank=True)
    price_description = models.TextField(
        "Описание тарифов", blank=True,
        help_text="Сезонные цены, тарифы номеров и условия оплаты. Числовую цену не заменяет.",
    )
    internal_notes = models.TextField(
        "Внутренние заметки", blank=True,
        help_text="Для менеджера и администратора. На публичных страницах не отображается.",
    )

    # Разделы карточки Joomla сохраняются отдельно, без извлечения чисел из текста.
    subtitle = models.CharField("Подзаголовок", max_length=255, blank=True)
    district_text = models.CharField("Район (текст)", max_length=255, blank=True)
    location_description = models.TextField("Месторасположение", blank=True)
    rooms_description = models.TextField("Номерной фонд / описание комнат", blank=True)
    meals_description = models.TextField("Питание", blank=True)
    beach_description = models.TextField("Пляж", blank=True)
    beach_distance_description = models.TextField("Расстояние до пляжа", blank=True)
    special_conditions = models.TextField("Особые условия", blank=True)
    additional_services = models.TextField("Дополнительные услуги", blank=True)
    booking_conditions = models.TextField("Условия бронирования", blank=True)
    checkin_checkout_description = models.TextField("Расчётный час", blank=True)
    included_services = models.TextField("Входит в стоимость", blank=True)
    paid_services = models.TextField("За дополнительную плату", blank=True)
    extra_beds_description = models.TextField("Дополнительные места", blank=True)

    # Цена
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Цена",
        help_text="Оставьте пустым, если цена неизвестна: будет показано «Цена по запросу»."
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='RUB',
        verbose_name="Валюта"
    )

    # Статусы
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name="Показывать на главной"
    )

    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default=AVAILABILITY_IN_STOCK,
        verbose_name='Наличие',
    )

    short_description = models.TextField(
        blank=True,
        verbose_name="Краткое описание"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Тип жилья",
    )

    meta_title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="SEO Title",
        help_text="Если не заполнено, будет использоваться название товара."
    )

    meta_description = models.TextField(
        blank=True,
        verbose_name="SEO Description",
        help_text="Описание страницы для поисковых систем."
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        verbose_name="Рейтинг",
    )

    reviews_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество отзывов",
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def seo_title(self):
        return self.meta_title or self.title

    @property
    def search_description(self):
        if self.meta_description:
            return self.meta_description
        if self.short_description:
            return self.short_description
        if self.description:
            return self.description[:160]
        return ""
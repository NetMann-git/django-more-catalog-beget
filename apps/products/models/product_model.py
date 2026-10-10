# apps/products/models/product_model.py
from django.db import models
from django.urls import reverse
from urllib.parse import urlsplit

from .badge import Badge
from .category import Category
from django.core.validators import MinValueValidator, MaxValueValidator
from ..map_data import validate_coordinates
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

    joomla_id = models.PositiveIntegerField("ID Joomla", null=True, blank=True, unique=True, editable=False)
    joomla_url = models.CharField("Исходный URL Joomla", max_length=1000, blank=True, editable=False)
    joomla_source = models.JSONField("Исходные данные JBZoo", default=dict, blank=True, editable=False)

    # Основная информация
    title = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="URL")

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
        verbose_name="Родительская категория (основная)",
        help_text="Основная категория объекта для переноса прежнего адреса. Это не родитель категории в дереве.",
    )
    
    categories = models.ManyToManyField(
        Category, blank=True, related_name="category_objects",
        verbose_name="Категории",
        help_text="Объект отображается во всех выбранных категориях. Основная категория включается автоматически.",
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

    map_coordinates = models.CharField(
        "Координаты метки", max_length=255, blank=True, validators=[validate_coordinates],
        help_text="Долгота, широта. Дробная часть через точку. Исходная точность сохраняется.",
    )
    map_center = models.CharField(
        "Центр карты", max_length=255, blank=True, validators=[validate_coordinates],
        help_text="Долгота, широта. Если не указан, карта центрируется на метке.",
    )
    map_zoom = models.PositiveSmallIntegerField(
        "Масштаб карты", default=12, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(19)],
        help_text="От 0 до 19. Если не указан, используется 12.",
    )
    map_source = models.JSONField(
        "Исходные данные карты JBZoo", default=dict, blank=True, editable=False,
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
        "Цены", blank=True,
        help_text="Сезонные цены, тарифы номеров и условия оплаты. Числовую цену не заменяет.",
    )
    price_description_source = models.TextField(
        "Исходный HTML цен", blank=True, editable=False,
        help_text="Архив первого непустого HTML. Не выводится публично.",
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
        if self.joomla_id and self.joomla_url:
            path = urlsplit(self.joomla_url).path.replace("//", "/")
            if path in {f"/{prefix}/{self.slug}.html" for prefix in (
                "properties-list", "gostevye-doma", "chastnyj-sektor-loo",
            )}:
                return path
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def seo_title(self):
        return self.meta_title or self.title

    def save(self, *args, **kwargs):
        """Архивировать первый HTML; дальнейшее редактирование не меняет архив."""
        capture = not self.price_description_source and bool(self.price_description)
        update_fields = kwargs.get("update_fields")
        if capture and (update_fields is None or "price_description" in update_fields):
            self.price_description_source = self.price_description
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"price_description_source"}
        return super().save(*args, **kwargs)

    @property
    def search_description(self):
        if self.meta_description:
            return self.meta_description
        if self.short_description:
            return self.short_description
        if self.description:
            return self.description[:160]
        return ""
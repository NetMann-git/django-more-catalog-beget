"""Материалы ZOO/JBZoo с независимыми категориями и исходным архивом."""
from django.db import models
from django.core.exceptions import ValidationError


class InformationCategory(models.Model):
    joomla_id = models.PositiveIntegerField('ID Joomla', unique=True, null=True, blank=True)
    title = models.CharField('Название', max_length=255)
    slug = models.SlugField('Псевдоним', max_length=255, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, verbose_name='Родительская категория')
    description = models.TextField('Описание', blank=True)
    sort_order = models.IntegerField('Порядок', default=0)
    is_published = models.BooleanField('Опубликована', default=True)
    meta_title = models.TextField('SEO-заголовок', blank=True)
    meta_description = models.TextField('SEO-описание', blank=True)
    source = models.JSONField('Исходные данные', default=dict, editable=False)

    class Meta:
        ordering = ('sort_order', 'title', 'pk')
        verbose_name = 'Категория материалов'
        verbose_name_plural = 'Категории материалов'

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        current = self.parent_id
        visited = {self.pk} if self.pk is not None else set()
        while current is not None:
            if current in visited:
                raise ValidationError({'parent': 'Категории не могут образовывать цикл.'})
            visited.add(current)
            current = InformationCategory.objects.filter(pk=current).values_list('parent_id', flat=True).first()


class InformationMaterial(models.Model):
    KINDS = (('info', 'Информационный материал'), ('map', 'Материал с картой'))
    joomla_id = models.PositiveIntegerField('ID Joomla', unique=True, null=True, blank=True)
    kind = models.CharField('Тип', max_length=10, choices=KINDS)
    title = models.CharField('Название', max_length=500)
    slug = models.SlugField('Псевдоним', max_length=255, unique=True)
    categories = models.ManyToManyField(InformationCategory, blank=True, related_name='materials', verbose_name='Категории')
    primary_category = models.ForeignKey(InformationCategory, null=True, blank=True, on_delete=models.PROTECT, related_name='primary_materials', verbose_name='Основная категория')
    map_mode = models.CharField('Состав карты', max_length=20, default='legacy',
        choices=(('legacy', 'Исходный курорт Joomla'), ('categories', 'Выбранные категории жилья')),
        help_text='Исходный курорт действует для десяти перенесённых карт. Для новой карты выберите категории жилья.')
    map_categories = models.ManyToManyField('products.Category', blank=True, related_name='information_maps',
        verbose_name='Категории жилья на карте',
        help_text='Используются в режиме «Выбранные категории жилья», вместе с опубликованными вложенными категориями. Пустой выбор даёт пустую карту.')
    subtitle = models.TextField('Подзаголовок', blank=True)
    intro = models.TextField('Анонс', blank=True)
    body = models.TextField('Текст', blank=True)
    extra_body = models.TextField('Дополнительный текст', blank=True)
    html_insert = models.TextField('Вставка HTML', blank=True)
    image_source = models.TextField('Исходное изображение', blank=True)
    legacy_url = models.TextField('Исходный адрес Joomla', blank=True)
    is_active = models.BooleanField('Опубликован', default=False)
    meta_title = models.TextField('SEO-заголовок', blank=True)
    meta_description = models.TextField('SEO-описание', blank=True)
    meta_keywords = models.TextField('SEO-ключевые слова', blank=True)
    meta_robots = models.CharField('SEO robots', max_length=255, blank=True)
    source = models.JSONField('Архив двух экспортов', default=dict, editable=False)

    class Meta:
        ordering = ('title', 'pk')
        verbose_name = 'Информационный материал'
        verbose_name_plural = 'Информационные материалы'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        from .legacy_urls import LEGACY_MATERIAL_PATHS
        return next((path for path, joomla_id in LEGACY_MATERIAL_PATHS.items() if joomla_id == self.joomla_id),
                    reverse('information:material', kwargs={'slug': self.slug}))

    @property
    def seo_title(self):
        return self.meta_title or self.title

    @property
    def search_description(self):
        from apps.products.seo_text import description_metadata
        return description_metadata(self.meta_description, self.intro, self.subtitle)

    @property
    def cover_url(self):
        from .media import media_url
        return media_url(self.image_source)

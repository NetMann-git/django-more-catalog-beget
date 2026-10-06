# apps/products/models/brand.py
from django.db import models
from django.urls import reverse


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="URL")
    logo = models.ImageField(
        upload_to="brands/",
        blank=True,
        null=True,
        verbose_name="Изображение типа жилья"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    country = models.CharField(max_length=100, blank=True, verbose_name="Страна")
    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Порядок",
        help_text="Меньшее число выводится раньше."
    )

    # SEO
    meta_title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="SEO Title",
        help_text="Если не заполнено, будет использоваться название типа жилья."
    )
    meta_description = models.TextField(
        blank=True,
        verbose_name="SEO Description",
        help_text="Краткое описание для поисковых систем."
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Тип жилья"
        verbose_name_plural = "Типы жилья"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:brand_detail", kwargs={"slug": self.slug})

    @property
    def seo_title(self):
        return self.meta_title or self.name

    @property
    def seo_description(self):
        return self.meta_description or self.description[:160] if self.description else ""
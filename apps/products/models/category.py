"""Категории жилья с сохранением структуры Joomla."""
from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="children", verbose_name="Родительская категория",
    )
    joomla_id = models.PositiveIntegerField(
        "ID Joomla", null=True, blank=True, unique=True, editable=False,
    )
    sort_order = models.IntegerField("Порядок", default=0)
    is_published = models.BooleanField("Опубликована", default=True)
    description = models.TextField("Описание HTML", blank=True)
    meta_title = models.TextField("SEO-заголовок", blank=True)
    meta_description = models.TextField("SEO-описание", blank=True)
    meta_keywords = models.TextField("SEO-ключевые слова", blank=True)
    joomla_source = models.JSONField(
        "Исходные поля Joomla", default=dict, blank=True, editable=False,
    )

    class Meta:
        ordering = ["sort_order", "title", "pk"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        current = self.parent_id
        visited = {self.pk} if self.pk is not None else set()
        while current is not None:
            if current in visited:
                raise ValidationError({"parent": "Категории не могут образовывать цикл."})
            visited.add(current)
            current = Category.objects.filter(pk=current).values_list("parent_id", flat=True).first()

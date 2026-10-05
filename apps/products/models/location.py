"""Географический справочник каталога жилья."""

from django.core.exceptions import ValidationError
from django.db import models


class Location(models.Model):
    """Регион, курорт или населённый пункт с родительской локацией."""

    name = models.CharField("Название", max_length=150)
    slug = models.SlugField("URL-код", max_length=180, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская локация",
    )
    description = models.TextField("Описание локации", blank=True)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "Локация"
        verbose_name_plural = "Локации"

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Запретить привязку к себе и к собственным потомкам."""
        super().clean()
        current = self.parent_id
        visited = {self.pk} if self.pk is not None else set()
        while current is not None:
            if current in visited:
                raise ValidationError({"parent": "Локации не могут образовывать цикл."})
            visited.add(current)
            current = (
                Location.objects.filter(pk=current)
                .values_list("parent_id", flat=True)
                .first()
            )

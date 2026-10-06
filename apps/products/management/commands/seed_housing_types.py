"""Начальное заполнение справочника типов жилья без замены старых записей."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.products.cache import CatalogCache
from apps.products.models import Brand

HOUSING_TYPES = (
    ("Частный сектор", "chastnyy-sektor"),
    ("Гостиницы", "gostinitsy"),
    ("Гостевые дома", "gostevye-doma"),
    ("Квартиры", "kvartiry"),
)


class Command(BaseCommand):
    help = "Добавить отсутствующие типы жилья, сохранив существующие записи."

    def handle(self, *args, **options):
        """Повторный запуск не создаёт дубликаты и не перезаписывает поля."""
        created = 0
        with transaction.atomic():
            for order, (name, slug) in enumerate(HOUSING_TYPES, start=1):
                if Brand.objects.filter(name=name).exists():
                    continue
                if Brand.objects.filter(slug=slug).exists():
                    raise CommandError(
                        f'Код «{slug}» уже занят другой записью. '
                        'Изменений не внесено; проверьте справочник вручную.'
                    )
                Brand.objects.create(name=name, slug=slug, sort_order=order * 10)
                created += 1
            transaction.on_commit(CatalogCache.clear_catalog)
        self.stdout.write(self.style.SUCCESS(f"Добавлено типов жилья: {created}."))

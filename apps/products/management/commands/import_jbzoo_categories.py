"""Импорт категорий: по умолчанию только проверка."""
from django.core.management.base import BaseCommand, CommandError
from apps.products.importing.categories import CategoryImportError, read_categories, import_categories


class Command(BaseCommand):
    help = "Импорт CSV/ZIP категорий JBZoo. Без --apply база не изменяется."

    def add_arguments(self, parser):
        parser.add_argument("source")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            rows = read_categories(options["source"])
            counts = import_categories(rows, apply=options["apply"])
        except (CategoryImportError, OSError, UnicodeError) as exc:
            raise CommandError(str(exc)) from exc
        mode = "Импорт выполнен" if options["apply"] else "Проверка без записи"
        self.stdout.write(f"{mode}: всего {len(rows)}; новых {counts['created']}; обновлений {counts['updated']}; без изменений {counts['unchanged']}.")

import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from apps.information.management.commands.audit_information_maps import read_only
from apps.products.category_coverage import category_coverage


class Command(BaseCommand):
    help = 'Показать опубликованное жильё, не входящее в информационные карты, и его категории.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Полный JSON-отчёт внутри patch-backups.')

    def handle(self, *args, **options):
        output = None
        if options['output']:
            root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
            output = Path(options['output']).resolve()
            if not output.is_relative_to(root) or output == root:
                raise CommandError('Отчёт необходимо сохранять в patch-backups.')
        with connection.execute_wrapper(read_only):
            report = category_coverage()
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        summary = {key: value for key, value in report.items() if key != 'outside_objects'}
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

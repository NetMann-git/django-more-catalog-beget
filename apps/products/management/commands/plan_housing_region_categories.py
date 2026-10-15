import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from apps.information.management.commands.audit_information_maps import read_only
from apps.products.region_proposals import region_proposals


class Command(BaseCommand):
    help = 'Подготовить предложения дополнительных категорий курортов, без изменения базы.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True, help='Полный JSON-план внутри patch-backups.')

    def handle(self, *args, **options):
        root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
        output = Path(options['output']).resolve()
        if not output.is_relative_to(root) or output == root:
            raise CommandError('План необходимо сохранять в patch-backups.')
        with connection.execute_wrapper(read_only):
            report = region_proposals()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write(json.dumps({key: value for key, value in report.items() if key != 'items'}, ensure_ascii=False, indent=2))

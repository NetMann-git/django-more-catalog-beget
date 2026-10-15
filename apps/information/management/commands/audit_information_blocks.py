"""Ведомость вставок Joomla для планирования их переноса."""
import json
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from apps.information.legacy_blocks import audit_information_blocks
from apps.products.management.commands.audit_housing_site import read_only


class Command(BaseCommand):
    help = 'Составить ведомость неподдерживаемых блоков Joomla без изменения базы и исполнения кода.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='JSON-отчёт внутри patch-backups; по умолчанию с датой.')
        parser.add_argument('--include-unpublished', action='store_true', help='Включить скрытые материалы.')
        parser.add_argument('--fail-on-unresolved', action='store_true', help='Завершиться с ошибкой, если остались неподдерживаемые блоки.')

    def handle(self, *args, **options):
        root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
        output = Path(options['output']).resolve() if options['output'] else root / ('information-blocks-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        if not output.is_relative_to(root):
            raise CommandError('Отчёт необходимо сохранять в patch-backups.')
        with connection.execute_wrapper(read_only):
            report = audit_information_blocks(options['include_unpublished'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write('Отчёт: ' + str(output))
        self.stdout.write(json.dumps({key: value for key, value in report.items() if key not in ('blocks', 'materials')}, ensure_ascii=False, indent=2))
        if options['fail_on_unresolved'] and not report['ok']:
            raise CommandError('Остались неподдерживаемые вставки Joomla. Ведомость сохранена.')

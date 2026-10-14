import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from apps.information.map_audit import audit_maps


def read_only(execute, sql, params, many, context):
    if sql.lstrip().split(None, 1)[0].upper() not in ('SELECT', 'EXPLAIN'):
        raise CommandError('Проверка карт запрещает SQL-записи.')
    return execute(sql, params, many, context)


class Command(BaseCommand):
    help = 'Проверить категории и координаты опубликованных информационных карт без изменения базы.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Путь JSON-отчёта внутри patch-backups.')

    def handle(self, *args, **options):
        output = None
        if options['output']:
            root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
            output = Path(options['output']).resolve()
            if not output.is_relative_to(root) or output == root:
                raise CommandError('Отчёт необходимо сохранять в patch-backups.')
        with connection.execute_wrapper(read_only):
            report = audit_maps()
        text = json.dumps(report, ensure_ascii=False, indent=2)
        self.stdout.write(text)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text + '\n', encoding='utf-8')
        if not report['ok']:
            raise CommandError('В настройках карт или координатах есть ошибки. См. JSON-отчёт.')

"""Первичный импорт материалов с обязательной SQLite-копией в patch-backups."""
import json
from django.core.management.base import BaseCommand
from apps.information.importing import load_plan, check_plan, import_plan


class Command(BaseCommand):
    help = 'Проверить или импортировать информационные материалы ZOO/JBZoo.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--check', action='store_true')
        group.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        plan = load_plan()
        check_plan(plan)
        if not options['apply']:
            self.stdout.write(json.dumps({'expected_categories': len(plan['categories']), 'expected_materials': len(plan['materials']), 'expected_published': sum(row['is_active'] for row in plan['materials']), 'shifted_rows_recovered': plan['shifted_rows_recovered'], 'ok': True}, ensure_ascii=False, indent=2))
            return
        from apps.information.backup import backup_database
        backup = backup_database()
        self.stdout.write('Резервная копия базы: ' + str(backup))
        self.stdout.write(json.dumps(import_plan(plan), ensure_ascii=False, indent=2))

import hashlib
import json
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.information.backup import backup_database
from apps.products.apply_region_categories import validate_plan, apply_plan


class Command(BaseCommand):
    help = 'Добавить дополнительные категории из проверяемого плана с резервной копией SQLite.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', required=True, help='JSON-план шага 69 в patch-backups.')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--check', action='store_true')
        group.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
        path = Path(options['plan']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise CommandError('План должен быть файлом внутри patch-backups.')
        try:
            raw = path.read_bytes()
            plan = json.loads(raw.decode('utf-8-sig'))
        except (ValueError, OSError) as exc:
            raise CommandError('Не удалось прочитать JSON-план.') from exc
        changes, unchanged = validate_plan(plan)
        summary = {'objects_in_plan': len(plan['items']), 'links_to_add': len(changes),
                   'already_applied': len(unchanged), 'applied': False}
        if options['apply'] and changes:
            backup = backup_database()
            journal = root / ('region-categories-step69-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
            report = {**summary, 'plan': str(path), 'plan_sha256': hashlib.sha256(raw).hexdigest(),
                      'database_backup': str(backup), 'state': 'prepared'}
            journal.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            try:
                result = apply_plan(plan)
            except Exception as exc:
                report.update(state='failed', error=str(exc))
                journal.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                raise CommandError(f'Добавление отменено. База: {backup}; журнал: {journal}') from exc
            report.update(result, state='completed', applied=True)
            journal.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            summary.update({key: value for key, value in result.items() if key != 'added'},
                           applied=True, database_backup=str(backup), journal=str(journal))
        elif options['apply']:
            summary.update(applied=True, added_links=0)
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

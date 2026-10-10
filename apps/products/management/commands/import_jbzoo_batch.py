"""Импорт явно выбранной партии из проверенного плана JBZoo."""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.products.importing.item import ItemImportError
from apps.products.importing.local_batch import import_local_batch, read_local_items
from .import_jbzoo_item import backup_database


class Command(BaseCommand):
    help = 'Импорт JBZoo партиями. --list показывает план; --batch N проверяет; --apply записывает.'

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true', help='Показать партии без изменения базы.')
        parser.add_argument('--batch', type=int, help='Номер одной партии.')
        parser.add_argument('--media-source', help='Папка, содержащая images/uploads/user_*.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        fixture = Path(__file__).resolve().parents[2] / 'fixtures/jbzoo_import_plan.json'
        try:
            plan = json.loads(fixture.read_text(encoding='utf-8'))
            if options['list']:
                if options['apply'] or options['batch'] is not None:
                    raise ItemImportError('--list нельзя сочетать с --batch или --apply.')
                self.stdout.write(json.dumps({
                    'source_date': plan['source_date'],
                    'ready_objects': sum(len(b['items']) for b in plan['batches']),
                    'previous_objects': len(plan['previous']),
                    'review_objects': len(plan['review']),
                    'batches': [{'number': b['number'], 'objects': [
                        {'id': d['id'], 'title': d['item']['name'],
                         'folder': 'images/uploads/' + d['gallery_folder'],
                         'url': d['url'], 'published': d['item']['state'] == '1'}
                        for d in b['items']]} for b in plan['batches']],
                }, ensure_ascii=False, indent=2))
                return
            selected = next((b for b in plan['batches'] if b['number'] == options['batch']), None)
            if selected is None:
                raise ItemImportError('Укажите номер партии --batch N из списка --list.')
            if not options['media_source']:
                raise ItemImportError('Укажите --media-source: папку с images/uploads.')
            approved = {d['id']: d['gallery_folder'] for d in selected['items']}
            batch = read_local_items(selected['items'], options['media_source'], approved)
            result = import_local_batch(batch, options['media_source'])
            backup = None
            report_path = None
            if options['apply']:
                folder = Path(settings.BASE_DIR) / 'patch-backups'
                folder.mkdir(exist_ok=True)
                if any(row['result'] != 'unchanged' for row in result):
                    backup = backup_database(folder, label=f'batch-{selected["number"]}')
                    self.stdout.write('Резервная копия: ' + str(backup))
                result = import_local_batch(batch, options['media_source'], apply=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
                report_path = folder / f'jbzoo-batch-{selected["number"]}-{stamp}.json'
            report = {'batch': selected['number'], 'apply': options['apply'],
                      'backup': str(backup) if backup else None, 'objects': result}
            if report_path:
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                self.stdout.write('Отчёт: ' + str(report_path))
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        except (ItemImportError, OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc

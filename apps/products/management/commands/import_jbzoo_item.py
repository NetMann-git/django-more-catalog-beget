"""Однообъектный пробный импорт; без --apply только проверка."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.products.importing.item import ItemImportError, import_item, prepare, read_snapshot


def backup_database(folder):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    if connection.vendor == 'sqlite':
        path = folder / f'db-before-item-2425-{stamp}.sqlite3'
        connection.ensure_connection()
        with sqlite3.connect(path) as target:
            connection.connection.backup(target)
    else:
        # Data backup includes all installed models. It does not replace a native DB dump.
        path = folder / f'data-before-item-2425-{stamp}.json'
        call_command('dumpdata', all=True, output=str(path), verbosity=0)
    return path


class Command(BaseCommand):
    help = 'Пробный импорт одного снимка JBZoo. Без --apply база и медиа не меняются.'

    def add_arguments(self, parser):
        parser.add_argument('--source', default=str(Path(__file__).resolve().parents[2] / 'fixtures/jbzoo_orion_2425.json'))
        parser.add_argument('--media-source', required=True, help='Папка, содержащая images/uploads/user_606.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            data = read_snapshot(options['source'])
            # This first patch deliberately accepts only the reviewed object.
            if data['id'] != 2425 or data['alias'] != 'gostevoj-dom-orion-po-ul-morskaya-2-b-v-olginke':
                raise ItemImportError('Шаг 23 предназначен только для проверенного объекта 2425.')
            _, _, _, _, unchanged = prepare(data, options['media_source'])
            folder = Path(settings.BASE_DIR) / 'patch-backups'
            if options['apply'] and not unchanged:
                folder.mkdir(exist_ok=True)
                backup = backup_database(folder)
                self.stdout.write(f'Резервная копия: {backup}')
            result = import_item(data, options['media_source'], apply=options['apply'])
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            if not result['gallery_complete']:
                self.stdout.write(self.style.WARNING('Галерея: в экспорте только папка user_606, список фотографий отсутствует. Импортированы главное фото и два видео. Остальные элементы сохранены в архиве JBZoo.'))
            if options['apply']:
                folder.mkdir(exist_ok=True)
                report = folder / ('item-2425-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.json')
                report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        except (ItemImportError, OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc

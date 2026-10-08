"""Импорт галереи «Ориона» с резервной копией и отчётом."""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.products.importing.gallery import import_gallery, read_images, read_manifest
from apps.products.importing.item import ItemImportError
from .import_jbzoo_item import backup_database


class Command(BaseCommand):
    help = 'Галерея объекта Joomla 2425. Без --apply только проверка; порядок по именам.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='ZIP или папка user_606.')
        parser.add_argument('--manifest', default=str(Path(__file__).resolve().parents[2] / 'fixtures/jbzoo_orion_2425_gallery.json'))
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            manifest = read_manifest(options['manifest'])
            blobs = read_images(options['source'], manifest)
            preview = import_gallery(manifest, blobs)
            folder = Path(settings.BASE_DIR) / 'patch-backups'
            if options['apply']:
                folder.mkdir(exist_ok=True)
                if preview['new_records'] or preview['new_files']:
                    self.stdout.write('Резервная копия: ' + str(backup_database(folder)))
            result = import_gallery(manifest, blobs, apply=options['apply']) if options['apply'] else preview
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            if options['apply']:
                stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
                report = folder / f'gallery-2425-{stamp}.json'
                report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                self.stdout.write('Отчёт: ' + str(report))
        except (ItemImportError, OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc

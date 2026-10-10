"""Двенадцать выбранных объектов: фотографии пользователь добавляет в патч сам."""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.products.importing.item import ItemImportError
from apps.products.importing.local_batch import import_local_batch, read_local_batch
from .import_jbzoo_item import backup_database


APPROVED = {1617: 'user_558', 1024: 'user_370', 887: 'user_232', 1965: 'user_300', 161: 'user_77', 185: 'user_101', 195: 'user_111', 1805: 'user_587', 1340: 'user_480', 1591: 'user_550', 917: 'user_256', 140: 'user_54'}


class Command(BaseCommand):
    help = 'Двенадцать объектов из JBZoo с локальными images/uploads/user_*. Без --apply только проверка.'

    def add_arguments(self, parser):
        parser.add_argument('--media-source', required=True, help='Корень распакованного патча, содержащий images/uploads.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        fixture = Path(__file__).resolve().parents[2] / 'fixtures/jbzoo_trial_twelve.json'
        try:
            batch = read_local_batch(fixture, options['media_source'], approved=APPROVED)
            result = import_local_batch(batch, options['media_source'])
            if options['apply']:
                folder = Path(settings.BASE_DIR) / 'patch-backups'
                folder.mkdir(exist_ok=True)
                if any(row['result'] != 'unchanged' for row in result):
                    self.stdout.write('Резервная копия: ' + str(backup_database(folder)))
                result = import_local_batch(batch, options['media_source'], apply=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
                path = folder / f'trial-twelve-{stamp}.json'
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                self.stdout.write('Отчёт: ' + str(path))
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        except (ItemImportError, OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc

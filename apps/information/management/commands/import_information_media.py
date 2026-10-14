"""Перенос исходных медиа с проверкой SHA-256 и журналом в patch-backups."""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.information.media import media_plan, local_path, file_hash
from apps.information.models import InformationMaterial


class Command(BaseCommand):
    help = 'Перенести images/... материалов из локальной папки без изменения качества.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='Папка, внутри которой находится images/.')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--check', action='store_true')
        group.add_argument('--apply', action='store_true')
        parser.add_argument('--allow-missing', action='store_true', help='Явно разрешить частичный перенос доступных файлов.')

    def handle(self, *args, **options):
        source = Path(options['source']).resolve()
        if not InformationMaterial.objects.exists():
            raise CommandError('Сначала выполните импорт информационных материалов.')
        plan = media_plan(InformationMaterial.objects.all(), source)
        folder = Path(settings.BASE_DIR) / 'patch-backups'
        folder.mkdir(parents=True, exist_ok=True)
        report = folder / ('information-media-step59-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        plan['created_files'] = []
        plan['applied'] = False
        def save_report():
            report.write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        save_report()
        self.stdout.write('Отчёт: ' + str(report))
        if options['apply']:
            if plan['conflicts']:
                raise CommandError('Есть отличающиеся существующие файлы. Ничего не перезаписано; см. отчёт.')
            if plan['missing_files'] and not options['allow_missing']:
                raise CommandError('Не все файлы найдены. Добавьте их или явно используйте --allow-missing.')
            root = Path(settings.MEDIA_ROOT) / 'joomla-information'
            for row in plan['entries']:
                if row['already_identical']:continue
                target = local_path(root, row['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name+'.information-step59.tmp')
                try:
                    if target.exists():raise CommandError('Файл появился после проверки: '+row['path'])
                    shutil.copyfile(local_path(source, row['path']), temporary)
                    if file_hash(temporary) != row['sha256']:
                        raise CommandError('Исходный файл изменился во время копирования: '+row['path'])
                    os.link(temporary, target)
                    plan['created_files'].append({'path': row['path'], 'sha256': row['sha256']})
                    save_report()
                finally:
                    if temporary.exists():temporary.unlink()
            plan['applied'] = True
            save_report()
        summary = {key: plan[key] for key in ('expected_files','available_files','already_identical','applied')}
        summary.update(created_files=len(plan['created_files']), missing_files=len(plan['missing_files']), conflicts=len(plan['conflicts']))
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

"""Отчёт ссылок материалов; проверка никогда не изменяет исходный HTML."""
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import override_settings
from apps.information.link_audit import audit_information_links
from apps.products.management.commands.audit_housing_site import read_only, original_thumbnailer


class Command(BaseCommand):
    help = 'Проверить внутренние ссылки текстов опубликованных материалов без сетевых запросов и SQL-записи.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='JSON-отчёт внутри patch-backups; по умолчанию создаётся автоматически.')

    def handle(self, *args, **options):
        root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
        output = Path(options['output']).resolve() if options['output'] else root / ('information-links-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        if not output.is_relative_to(root):
            raise CommandError('Отчёт необходимо сохранять в patch-backups.')
        with override_settings(ALLOWED_HOSTS=['audit.local'], SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
                               CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}):
            with patch('easy_thumbnails.templatetags.thumbnail.get_thumbnailer', side_effect=original_thumbnailer), connection.execute_wrapper(read_only):
                report = audit_information_links()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write('Отчёт: ' + str(output))
        summary = {key: value for key, value in report.items() if key not in ('issues', 'unchecked_links', 'redirected_links')}
        summary.update(issues=len(report['issues']), unchecked_links=len(report['unchecked_links']), redirected_links=len(report['redirected_links']))
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        if not report['ok']:
            raise CommandError('Обнаружены проблемные ссылки. Подробности сохранены в JSON-отчёте.')

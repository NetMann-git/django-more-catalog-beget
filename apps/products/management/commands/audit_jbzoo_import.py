"""Проверка полноты импорта без изменения базы и файлов."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.products.importing.media_paths import valid_media_path
from apps.products.models import Product


def load_plan():
    path = Path(__file__).resolve().parents[2] / 'fixtures/jbzoo_import_plan.json'
    plan = json.loads(path.read_text(encoding='utf-8'))
    urls = json.loads(path.with_name('jbzoo_previous_urls.json').read_text(encoding='utf-8'))
    for row in plan['previous']:
        row['url'] = urls[str(row['id'])]
    return plan


def audit(plan, verify_hashes=False):
    expected = {row['id']: row for row in plan['previous']}
    expected.update({row['id']: row for batch in plan['batches'] for row in batch['items']})
    products = list(Product.objects.filter(joomla_id__isnull=False))
    found = {}
    issues = []
    root = Path(settings.MEDIA_ROOT).resolve()
    checked = set()
    for obj in products:
        if obj.joomla_id in found:
            issues.append({'id': obj.joomla_id, 'problem': 'duplicate_id'})
        found[obj.joomla_id] = obj
        row = expected.get(obj.joomla_id)
        if row is None:
            issues.append({'id': obj.joomla_id, 'problem': 'unexpected_id'})
            continue
        if obj.slug != row['alias']:
            issues.append({'id': obj.joomla_id, 'problem': 'alias_mismatch', 'expected': row['alias'], 'actual': obj.slug})
        if row.get('url'):
            url = urlsplit(row['url']).path.replace('//', '/')
            if obj.get_absolute_url() != url:
                issues.append({'id': obj.joomla_id, 'problem': 'url_mismatch', 'expected': url, 'actual': obj.get_absolute_url()})
        source = obj.joomla_source
        if not isinstance(source, dict) or source.get('id') != obj.joomla_id:
            issues.append({'id': obj.joomla_id, 'problem': 'missing_source_archive'})
            continue
        if row.get('item') is not None and source.get('item') != row['item']:
            issues.append({'id': obj.joomla_id, 'problem': 'source_archive_mismatch'})
        media = source.get('media', [])
        if not isinstance(media, list):
            issues.append({'id': obj.joomla_id, 'problem': 'invalid_media_archive'})
            continue
        for entry in media:
            rel = entry.get('path') if isinstance(entry, dict) else None
            if not isinstance(rel, str) or not valid_media_path(rel, obj.joomla_id):
                issues.append({'id': obj.joomla_id, 'problem': 'unsafe_archived_path'})
                continue
            name = 'jbzoo/' + str(obj.joomla_id) + '/' + rel
            file = (root / name).resolve()
            if not file.is_relative_to(root):
                issues.append({'id': obj.joomla_id, 'problem': 'unsafe_archived_path'})
                continue
            checked.add(name)
            if not file.is_file():
                issues.append({'id': obj.joomla_id, 'problem': 'missing_media', 'file': name})
            elif file.stat().st_size != entry.get('size'):
                issues.append({'id': obj.joomla_id, 'problem': 'media_size_mismatch', 'file': name})
            elif verify_hashes:
                with file.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != entry.get('sha256'):
                    issues.append({'id': obj.joomla_id, 'problem': 'media_hash_mismatch', 'file': name})
    missing = sorted(set(expected) - set(found))
    return {
        'expected_objects': len(expected), 'imported_objects': len(products),
        'published_objects': sum(obj.is_active for obj in products),
        'missing_ids': missing, 'archived_placeholders': len(plan['review']),
        'media_files_checked': len(checked), 'hashes_checked': verify_hashes,
        'issues': issues, 'ok': not missing and not issues,
    }


class Command(BaseCommand):
    help = 'Проверить ID, алиасы, старые URL и архивные медиа Joomla без изменения данных.'

    def add_arguments(self, parser):
        parser.add_argument('--verify-hashes', action='store_true', help='Сверить SHA-256 всех импортированных файлов.')
        parser.add_argument('--fail-on-errors', action='store_true', help='Завершить с ненулевым кодом при расхождениях.')

    def handle(self, *args, **options):
        try:
            report = audit(load_plan(), options['verify_hashes'])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if options['fail_on_errors'] and not report['ok']:
            raise CommandError('Проверка обнаружила отсутствующие объекты или расхождения; подробности выше.')

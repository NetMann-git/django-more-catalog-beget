"""Аудит обнаруживает пропуски и повреждения, не изменяя данные."""
import hashlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.products.models import Product
from apps.products.management.commands.audit_jbzoo_import import audit, load_plan


class ImportAuditTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.override = override_settings(MEDIA_ROOT=self.root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.row = {'id': 1, 'alias': 'house', 'url': 'https://example.com/properties-list/house.html'}
        self.plan = {'previous': [], 'batches': [{'items': [self.row]}], 'review': []}
        self.rel = 'images/uploads/user_1/photo.jpg'
        self.file = self.root / 'jbzoo/1' / self.rel
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b'original')
        self.source = {'id': 1, 'url': self.row['url'], 'media': [{'path': self.rel, 'size': 8, 'sha256': hashlib.sha256(b'original').hexdigest()}]}
        self.product = Product.objects.create(title='House', slug='house', joomla_id=1, joomla_url=self.row['url'], price=None, joomla_source=self.source)

    def test_success_and_missing_ids_no_writes(self):
        before = self.product.joomla_source.copy()
        self.assertTrue(audit(self.plan, True)['ok'])
        self.plan['previous'].append({'id': 2, 'alias': 'missing'})
        report = audit(self.plan, True)
        self.assertEqual(report['missing_ids'], [2])
        self.product.refresh_from_db()
        self.assertEqual(self.product.joomla_source, before)
        self.assertEqual(self.file.read_bytes(), b'original')

    def test_equal_size_corruption_requires_hash_check(self):
        self.file.write_bytes(b'changed!')
        self.assertTrue(audit(self.plan)['ok'])
        self.assertEqual(audit(self.plan, True)['issues'][0]['problem'], 'media_hash_mismatch')

    def test_missing_file_alias_and_url_detected(self):
        self.file.unlink()
        self.product.slug = 'changed'
        self.product.save()
        problems = {x['problem'] for x in audit(self.plan)['issues']}
        self.assertIn('missing_media', problems)
        self.assertIn('alias_mismatch', problems)
        self.assertIn('url_mismatch', problems)

    def test_unsafe_archive_path_not_opened(self):
        self.source['media'][0]['path'] = '../../outside.jpg'
        self.product.joomla_source = self.source
        self.product.save()
        self.assertEqual(audit(self.plan, True)['issues'][0]['problem'], 'unsafe_archived_path')

    def test_command_outputs_report_and_optional_failure_status(self):
        self.file.unlink()
        output = io.StringIO()
        with patch('apps.products.management.commands.audit_jbzoo_import.load_plan', return_value=self.plan):
            call_command('audit_jbzoo_import', stdout=output)
            self.assertFalse(json.loads(output.getvalue())['ok'])
            with self.assertRaises(CommandError):
                call_command('audit_jbzoo_import', fail_on_errors=True, stdout=io.StringIO())

    def test_full_plan_has_548_unique_ids_with_source_urls(self):
        plan = load_plan()
        rows = plan['previous'] + [d for b in plan['batches'] for d in b['items']]
        self.assertEqual(len(rows), 548)
        self.assertEqual(len({d['id'] for d in rows}), 548)
        self.assertTrue(all(d.get('url') for d in rows))

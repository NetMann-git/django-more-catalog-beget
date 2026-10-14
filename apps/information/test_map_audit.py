import io
import json
import tempfile
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from apps.products.models import Category, Product
from .models import InformationMaterial
from .map_audit import audit_maps
from .maps import material_map


class MapAuditTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Курорт', slug='resort', joomla_id=73)
        self.material = InformationMaterial.objects.create(title='Карта', slug='map', kind='map',
            map_mode='categories', is_active=True)
        self.material.map_categories.add(self.category)

    def product(self, slug, coordinates, **kwargs):
        return Product.objects.create(title=slug, slug=slug, category=self.category,
            map_coordinates=coordinates, is_active=kwargs.pop('is_active', True), **kwargs)

    def test_counts_match_public_map_and_deduplicate_across_maps(self):
        a = self.product('first', '39,43')
        self.product('second', '39.0,43.000')
        absent = self.product('absent', '')
        bad = self.product('invalid', 'NaN,43')
        self.product('hidden', 'NaN,43', is_active=False)
        a.categories.add(self.category)
        other = InformationMaterial.objects.create(title='Карта 2', slug='map2', kind='map',
            map_mode='categories', is_active=True)
        other.map_categories.add(self.category)
        report = audit_maps()
        self.assertEqual(report['unique_objects_checked'], 4)
        self.assertEqual(report['unique_objects_without_coordinates'], 1)
        self.assertEqual(report['unique_objects_with_invalid_coordinates'], 1)
        self.assertFalse(report['ok'])
        row = report['maps'][0]
        self.assertEqual(row['points'], len(material_map(self.material)['points']))
        self.assertEqual(row['coincident_groups'], 1)
        self.assertEqual(row['missing_coordinates'], [absent.pk])
        self.assertEqual(row['invalid_coordinates'], [bad.pk])

    def test_configuration_errors_and_warnings(self):
        self.material.map_categories.clear()
        report = audit_maps()
        self.assertTrue(report['ok'])
        self.assertIn('no_categories_selected', [r['code'] for r in report['warnings']])
        self.material.map_categories.add(self.category)
        self.category.is_published = False; self.category.save()
        self.assertIn('categories_not_public', [r['code'] for r in audit_maps()['warnings']])
        self.material.map_mode = 'legacy'; self.material.joomla_id = 836; self.material.save()
        self.assertTrue(audit_maps()['ok'])
        self.category.delete()
        self.assertEqual(audit_maps()['issues'][0]['code'], 'missing_legacy_categories')
        self.material.joomla_id = 9999; self.material.save()
        self.assertEqual(audit_maps()['issues'][0]['code'], 'legacy_map_not_configured')
        self.material.is_active = False; self.material.save()
        self.assertEqual(audit_maps()['published_maps'], 0)

    def test_command_report_and_no_database_writes(self):
        bad = self.product('bad', '181,43')
        before = Product.objects.get(pk=bad.pk).map_coordinates
        with tempfile.TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            output = Path(folder) / 'patch-backups' / 'maps.json'
            with self.assertRaises(CommandError):
                call_command('audit_information_maps', output=str(output), stdout=io.StringIO())
            report = json.loads(output.read_text())
            self.assertFalse(report['ok'])
            with self.assertRaises(CommandError):
                call_command('audit_information_maps', output=str(Path(folder) / 'outside.json'), stdout=io.StringIO())
            self.assertFalse((Path(folder) / 'outside.json').exists())
        self.assertEqual(Product.objects.get(pk=bad.pk).map_coordinates, before)

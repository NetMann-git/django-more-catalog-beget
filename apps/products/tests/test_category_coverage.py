import io
import json
import tempfile
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from apps.information.models import InformationMaterial
from apps.products.category_coverage import category_coverage
from apps.products.models import Category, Product


class CoverageTests(TestCase):
    def test_reasons_multiple_categories_hidden_parent_and_map_deduplication(self):
        region = Category.objects.create(title='Адлер', slug='region', joomla_id=73)
        child = Category.objects.create(title='Номера', slug='child', parent=region)
        outside = Category.objects.create(title='Другой раздел', slug='outside')
        hidden = Category.objects.create(title='Скрытый', slug='hidden', is_published=False)
        hidden_child = Category.objects.create(title='Дочерняя', slug='hidden-child', parent=hidden)
        for slug in ('map-one', 'map-two'):
            m = InformationMaterial.objects.create(title=slug, slug=slug, kind='map', map_mode='categories', is_active=True)
            m.map_categories.add(region)
        good = Product.objects.create(title='Дом', slug='home', category=outside, is_active=True)
        good.categories.add(region, child)
        Product.objects.create(title='Без категорий', slug='none', is_active=True)
        Product.objects.create(title='Скрытый раздел', slug='hidden-category', category=hidden_child, is_active=True)
        Product.objects.create(title='Другой раздел', slug='other', category=outside, is_active=True)
        Product.objects.create(title='Скрытый объект', slug='inactive', category=outside, is_active=False)
        report = category_coverage()
        self.assertEqual(report['published_objects'], 4)
        self.assertEqual(report['objects_covered_by_maps'], 1)
        self.assertEqual(report['objects_outside_maps'], 3)
        self.assertEqual(list(report['outside_map_reasons'].values()), [1, 1, 1])
        self.assertEqual([row['objects'] for row in report['maps']], [1, 1])
        category = next(row for row in report['categories'] if row['id'] == outside.pk)
        self.assertEqual(category['published_objects_assigned'], 2)
        self.assertEqual(category['objects_outside_maps'], 1)
        self.assertFalse(next(row for row in report['categories'] if row['id'] == hidden_child.pk)['public'])

    def test_command_writes_full_report_only_inside_backup_directory(self):
        product = Product.objects.create(title='Дом', slug='house', is_active=True)
        with tempfile.TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            output = Path(folder) / 'patch-backups' / 'coverage.json'
            stdout = io.StringIO()
            call_command('audit_housing_category_coverage', output=str(output), stdout=stdout)
            report = json.loads(output.read_text())
            self.assertEqual(report['outside_objects'][0]['id'], product.pk)
            self.assertNotIn('outside_objects', json.loads(stdout.getvalue()))
            with self.assertRaises(CommandError):
                call_command('audit_housing_category_coverage', output=str(Path(folder) / 'wrong.json'), stdout=io.StringIO())
        product.refresh_from_db()
        self.assertIsNone(product.category_id)
        self.assertEqual(product.categories.count(), 0)

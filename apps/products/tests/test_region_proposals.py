import io
import json
import tempfile
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from apps.products.models import Category, Product
from apps.products.region_proposals import proposal, region_proposals


class RegionProposalTests(TestCase):
    def setUp(self):
        self.adler = Category.objects.create(title='Адлер', slug='adler', joomla_id=73)
        self.abhaz = Category.objects.create(title='Абхазия', slug='abhaz', joomla_id=84)
        self.general = Category.objects.create(title='Дополнительно', slug='extra', joomla_id=93)
        self.categories = {73: self.adler, 84: self.abhaz}

    def product(self, title='Дом в Адлере', **kwargs):
        return Product.objects.create(title=title, slug='house', category=self.general, is_active=True, **kwargs)

    def test_proposal_preserves_source_url_primary_and_all_links(self):
        p = self.product(address='г. Сочи, Адлер', map_coordinates='39.9,43.4',
                         joomla_source={'item': {'tags': {'0': 'Адлер', '1': 'Большое Сочи'}}})
        p.categories.add(self.general)
        row = proposal(p, self.categories)
        self.assertEqual(row['status'], 'proposed')
        self.assertEqual(row['suggested_category_id'], self.adler.pk)
        self.assertEqual(row['candidate_region_joomla_ids'], [73])
        self.assertEqual(row['coordinate_status'], 'valid')
        self.assertEqual(row['primary_category_id'], self.general.pk)
        self.assertEqual(row['existing_category_ids'], [self.general.pk])
        self.assertEqual(len(row['snapshot_sha256']), 64)
        p.refresh_from_db()
        self.assertEqual(p.category_id, self.general.pk)
        self.assertEqual(list(p.categories.all()), [self.general])
        self.assertEqual(row['url'], p.get_absolute_url())

    def test_conflict_missing_category_and_coordinates_never_resolve_region(self):
        p = self.product(joomla_source={'item': {'tags': {'0': 'Абхазия'}}}, map_coordinates='39.9,43.4')
        self.assertEqual(proposal(p, self.categories)['reason'], 'conflicting_regions')
        p.title = 'Дом'; p.joomla_source = {'item': {'tags': {'0': 'Большое Сочи'}}}
        self.assertEqual(proposal(p, self.categories)['reason'], 'no_specific_region')
        p.title = 'Дом в Лоо'; p.map_coordinates = 'NaN,43'
        row = proposal(p, self.categories)
        self.assertEqual(row['reason'], 'target_category_not_public_or_missing')
        self.assertEqual(row['coordinate_status'], 'invalid')
        self.assertIsNone(row['coordinate_check_url'])

    def test_command_plan_is_read_only_and_output_is_restricted(self):
        p = self.product()
        with tempfile.TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            output = Path(folder) / 'patch-backups' / 'plan.json'
            stdout = io.StringIO()
            call_command('plan_housing_region_categories', output=str(output), stdout=stdout)
            report = json.loads(output.read_text())
            self.assertEqual(report['proposed_objects'], 1)
            self.assertFalse(report['applied'])
            self.assertNotIn('items', json.loads(stdout.getvalue()))
            with self.assertRaises(CommandError):
                call_command('plan_housing_region_categories', output=str(Path(folder) / 'wrong.json'))
        p.refresh_from_db()
        self.assertEqual(p.categories.count(), 0)
        self.assertEqual(p.category_id, self.general.pk)

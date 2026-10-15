import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from apps.products.models import Category, Product
from apps.products.region_proposals import proposal
from apps.products.apply_region_categories import validate_plan, apply_plan


class ApplyRegionTests(TestCase):
    def setUp(self):
        self.region = Category.objects.create(title='Кудепста', slug='kudepsta', joomla_id=77)
        self.hosta = Category.objects.create(title='Хоста', slug='hosta', joomla_id=114)
        self.general = Category.objects.create(title='Все варианты', slug='all', joomla_id=21)
        self.product = Product.objects.create(title='Частный сектор в Кудепсте', slug='house',
            address='Кудепста, переулок Тихий, д. 9', district_text='Хостинский район — Кудепста ( центр )',
            joomla_source={'item': {'tags': {'0': 'Кудепста'}}}, category=self.general, is_active=True)
        self.product.categories.add(self.general)
        self.categories = {77: self.region, 114: self.hosta}

    def plan(self, products=None):
        rows = [proposal(p, self.categories) for p in products or [self.product]]
        return {'schema': 2, 'applied': False, 'objects_outside_maps': len(rows), 'items': rows}

    def test_administrative_district_is_not_resort_and_apply_is_idempotent(self):
        plan = self.plan()
        self.assertEqual(plan['items'][0]['status'], 'proposed')
        self.assertEqual(plan['items'][0]['suggested_category_id'], self.region.pk)
        original = Product.objects.values().get(pk=self.product.pk)
        self.assertEqual(apply_plan(plan)['added_links'], 1)
        self.assertEqual(apply_plan(plan)['already_applied'], 1)
        self.assertEqual(set(self.product.categories.values_list('pk', flat=True)), {self.general.pk, self.region.pk})
        self.assertEqual(original, Product.objects.values().get(pk=self.product.pk))
        p = Product(title='Дом', slug='district-only', district_text='Хостинский район')
        # Нельзя назначить Хосту по одному названию административного района.
        p.pk = 999
        self.assertEqual(proposal(p, self.categories)['status'], 'review')

    def test_stale_state_hidden_target_tampering_and_old_schema_are_rejected(self):
        plan = self.plan()
        self.product.address = 'Другой адрес'; self.product.save()
        with self.assertRaises(CommandError): validate_plan(plan)
        plan = self.plan()
        plan['items'][0]['suggested_category_id'] = self.hosta.pk
        with self.assertRaises(CommandError): validate_plan(plan)
        plan = self.plan()
        self.region.is_published = False; self.region.save()
        with self.assertRaises(CommandError): validate_plan(plan)
        with self.assertRaises(CommandError): validate_plan({'schema': 1, 'applied': False, 'items': []})
        self.assertEqual(self.product.categories.count(), 1)

    def test_transaction_rolls_back_if_second_link_fails(self):
        other = Product.objects.create(title='Дом в Кудепсте', slug='other', category=self.general, is_active=True)
        plan = self.plan([self.product, other])
        manager = type(self.product.categories)
        original = manager.add
        def fail_second(instance, *args, **kwargs):
            original(instance, *args, **kwargs)
            if instance.instance.pk == other.pk:
                raise RuntimeError('test failure')
        with patch.object(manager, 'add', fail_second), self.assertRaises(RuntimeError): apply_plan(plan)
        self.assertEqual(set(self.product.categories.values_list('pk', flat=True)), {self.general.pk})
        self.assertEqual(other.categories.count(), 0)

    def test_check_and_apply_command_backup_journal_and_repeat(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            root = Path(folder) / 'patch-backups'; root.mkdir()
            path = root / 'plan.json'; path.write_text(json.dumps(self.plan()))
            target = 'apps.products.management.commands.apply_housing_region_categories.backup_database'
            with patch(target, return_value=root / 'database.sqlite3') as backup:
                call_command('apply_housing_region_categories', plan=str(path), check=True, stdout=io.StringIO())
                backup.assert_not_called()
                self.assertEqual(self.product.categories.count(), 1)
                call_command('apply_housing_region_categories', plan=str(path), apply=True, stdout=io.StringIO())
                backup.assert_called_once()
                journal = json.loads(next(root.glob('region-categories-step69-*.json')).read_text())
                self.assertTrue(journal['applied'])
                self.assertEqual(journal['added_links'], 1)
                call_command('apply_housing_region_categories', plan=str(path), apply=True, stdout=io.StringIO())
                backup.assert_called_once()
            with self.assertRaises(CommandError):
                call_command('apply_housing_region_categories', plan=str(Path(folder) / 'plan.json'), check=True)

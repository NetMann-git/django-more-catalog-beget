"""Проверки сохранности, повторного импорта и отказа при конфликтах."""
import csv
import io
import tempfile
from copy import deepcopy
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.products.importing.categories import CategoryImportError, import_categories, read_categories
from apps.products.models import Category, Product

SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_categories_2026_10_06.csv'


class CategoryImportTests(TestCase):
    def setUp(self):
        self.rows = read_categories(SOURCE)

    def read_modified(self, modify):
        rows = deepcopy(self.rows)
        modify(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'categories.csv'
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            return read_categories(path)

    def test_actual_export_and_default_dry_run(self):
        self.assertEqual(len(self.rows), 38)
        out = io.StringIO()
        call_command('import_jbzoo_categories', str(SOURCE), stdout=out)
        self.assertEqual(Category.objects.count(), 0)
        self.assertIn('Проверка без записи', out.getvalue())

    def test_full_import_and_repeat_preserve_every_source_field(self):
        first = import_categories(self.rows, apply=True)
        self.assertEqual(first['created'], 38)
        self.assertEqual(Category.objects.count(), 38)
        for row in self.rows:
            category = Category.objects.get(joomla_id=int(row['id']))
            self.assertEqual(category.joomla_source, row)
            self.assertEqual(category.description, row['description'])
            self.assertEqual(category.meta_title, row['metadata_title'])
            self.assertEqual(category.parent.slug if category.parent else '', row['parent'])
        ids = dict(Category.objects.values_list('joomla_id', 'pk'))
        repeat = import_categories(self.rows, apply=True)
        self.assertEqual(repeat, {'created': 0, 'updated': 0, 'unchanged': 38})
        self.assertEqual(dict(Category.objects.values_list('joomla_id', 'pk')), ids)

    def test_slug_adoption_preserves_product_fk_and_unrelated_categories(self):
        existing = Category.objects.create(title='Старое название', slug='hosta')
        other = Category.objects.create(title='Не из экспорта', slug='other')
        product = Product.objects.create(title='Жильё', slug='house', category=existing, price=None)
        import_categories(self.rows, apply=True)
        product.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(product.category_id, existing.pk)
        self.assertEqual(existing.joomla_id, 114)
        self.assertTrue(Category.objects.filter(pk=other.pk).exists())

    def test_updates_and_dry_run_no_write(self):
        import_categories(self.rows, apply=True)
        rows = deepcopy(self.rows)
        rows[0]['name'] = 'Изменённое название'
        self.assertEqual(import_categories(rows)['updated'], 1)
        self.assertNotEqual(Category.objects.get(joomla_id=19).title, rows[0]['name'])
        self.assertEqual(import_categories(rows, apply=True)['updated'], 1)
        self.assertEqual(Category.objects.get(joomla_id=19).title, rows[0]['name'])

    def test_changed_alias_conflict_stops_all_writes(self):
        existing = Category.objects.create(title='Изменено', slug='changed', joomla_id=114)
        with self.assertRaises(CategoryImportError):
            import_categories(self.rows, apply=True)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Category.objects.get().pk, existing.pk)

    def test_slug_claimed_by_other_joomla_id(self):
        Category.objects.create(title='Конфликт', slug='hosta', joomla_id=999)
        with self.assertRaises(CategoryImportError):
            import_categories(self.rows, apply=True)
        self.assertEqual(Category.objects.count(), 1)

    def test_duplicate_names_allowed(self):
        Category.objects.create(title='Жильё', slug='a')
        Category.objects.create(title='Жильё', slug='b')
        self.assertEqual(Category.objects.count(), 2)

    def test_duplicate_id_alias_missing_parent_and_cycle_rejected(self):
        for modify in (
            lambda r: r[0].update(id=r[1]['id']),
            lambda r: r[0].update(alias=r[1]['alias']),
            lambda r: r[0].update(parent='missing'),
            lambda r: r[0].update(parent=r[0]['alias']),
            lambda r: (r[0].update(parent=r[1]['alias']), r[1].update(parent=r[0]['alias'])),
            lambda r: r[0].update(published='yes'),
        ):
            with self.subTest(modify=modify), self.assertRaises(CategoryImportError):
                self.read_modified(modify)

    def test_model_parent_validation(self):
        root = Category.objects.create(title='Корень', slug='root')
        child = Category.objects.create(title='Дочерняя', slug='child', parent=root)
        root.parent = child
        with self.assertRaises(ValidationError):
            root.full_clean()

    def test_cli_missing_source_is_readable_error(self):
        with self.assertRaises(CommandError):
            call_command('import_jbzoo_categories', '/missing/export.csv')

from copy import deepcopy
from django.test import TestCase
from django.core.management.base import CommandError
from .models import InformationMaterial, InformationCategory
from .importing import load_plan, import_plan, check_plan
from .admin import MaterialForm


class InformationImportTests(TestCase):
    def test_full_import_and_originals(self):
        plan = load_plan()
        report = import_plan(plan)
        self.assertEqual(report['materials'], 193)
        self.assertEqual(report['categories'], 14)
        self.assertEqual(report['published'], 191)
        self.assertEqual(InformationMaterial.objects.filter(kind='map').count(), 10)
        self.assertEqual(plan['shifted_rows_recovered'], 75)
        for row in plan['materials']:
            obj = InformationMaterial.objects.get(joomla_id=row['joomla_id'])
            self.assertEqual(obj.source, row['source'])
            self.assertEqual(obj.body, row['body'])
            self.assertEqual(obj.legacy_url, row['legacy_url'])
            self.assertEqual(set(obj.categories.values_list('slug', flat=True)), set(row['category_slugs']))

    def test_repeat_preserves_edits(self):
        plan = load_plan()
        import_plan(plan)
        obj = InformationMaterial.objects.first()
        obj.title = 'Исправленный текст'
        obj.save()
        report = import_plan(plan)
        self.assertEqual(report['new_materials'], 0)
        self.assertEqual(report['new_categories'], 0)
        obj.refresh_from_db()
        self.assertEqual(obj.title, 'Исправленный текст')

    def test_conflict_does_not_overwrite_or_partially_import(self):
        plan = load_plan()
        row = plan['materials'][0]
        InformationMaterial.objects.create(joomla_id=row['joomla_id'], title=row['title'], slug=row['slug'], kind=row['kind'], source={'different': True})
        with self.assertRaises(CommandError):
            import_plan(plan)
        self.assertEqual(InformationCategory.objects.count(), 0)
        self.assertEqual(InformationMaterial.objects.count(), 1)

    def test_unknown_category_and_editor(self):
        plan = deepcopy(load_plan())
        plan['materials'][0]['category_slugs'] = ['missing']
        with self.assertRaises(CommandError):
            check_plan(plan)
        form = MaterialForm()
        self.assertIn('tinymce.min.js', str(form.media))
        self.assertIn('data-prices-editor', str(form['body']))

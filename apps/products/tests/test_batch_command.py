"""Выбор партии должен быть явным; просмотр плана не требует фотографий."""
import io
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from apps.products.models import Product


class BatchCommandTests(TestCase):
    def test_list_is_read_only_and_accounts_for_export(self):
        import json
        output = io.StringIO()
        call_command('import_jbzoo_batch', list=True, stdout=output)
        plan = json.loads(output.getvalue())
        self.assertEqual(plan['ready_objects'] + plan['previous_objects'] + plan['review_objects'], 550)
        self.assertEqual([len(b['objects']) for b in plan['batches']], [10, 10, 10, 10, 4])
        self.assertFalse(Product.objects.exists())

    def test_apply_requires_one_valid_batch_and_media_source(self):
        for options in ({'apply': True}, {'batch': 0}, {'batch': 999},
                        {'batch': 1}, {'list': True, 'apply': True}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command('import_jbzoo_batch', stdout=io.StringIO(), **options)
        self.assertFalse(Product.objects.exists())

import io
import json
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.sessions.models import Session
from django.test import TestCase, Client
from apps.products.models import Product


class HousingSiteAuditTests(TestCase):
    def test_audit_passes_without_session_or_product_writes(self):
        product = Product.objects.create(title='Дом', slug='house', price=None, joomla_id=9911)
        before = Session.objects.count()
        output = io.StringIO()
        call_command('audit_housing_site', stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report['ok'])
        self.assertEqual(report['published_objects'], 1)
        self.assertEqual(Session.objects.count(), before)
        product.refresh_from_db()
        self.assertEqual(product.title, 'Дом')

    def test_wrong_canonical_is_reported(self):
        product = Product.objects.create(title='Дом', slug='house', price=None)
        original = Client.get
        def broken(client, path, *args, **kwargs):
            response = original(client, path, *args, **kwargs)
            if path == product.get_absolute_url():
                response.content = response.content.replace(b'rel="canonical"', b'rel="wrong"')
            return response
        output = io.StringIO()
        with patch.object(Client, 'get', broken), self.assertRaises(CommandError):
            call_command('audit_housing_site', stdout=output)
        self.assertIn('canonical_mismatch', output.getvalue())

    def test_output_must_be_in_patch_backups(self):
        with self.assertRaisesMessage(CommandError, 'patch-backups'):
            call_command('audit_housing_site', output='outside-report.json')

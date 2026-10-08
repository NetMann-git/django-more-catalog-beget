"""Проверки безопасного переноса выбранного реального объекта JBZoo."""
import copy
import hashlib
import tempfile
from unittest.mock import patch
from pathlib import Path

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.products.importing.item import ItemImportError, import_item, read_snapshot
from apps.products.models import Brand, Category, Product
from apps.products.prices_html import sanitize_prices
from apps.users.models import Profile
from apps.users.constants import ROLE_MANAGER


class ItemImportTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / 'source'
        self.target = root / 'target'
        self.settings = override_settings(MEDIA_ROOT=self.target)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_orion_2425.json'
        self.data = read_snapshot(fixture)
        for entry in self.data['media']:
            path = self.source / entry['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture-media')
            entry['sha256'] = hashlib.sha256(b'fixture-media').hexdigest()
        for slug in ('vse-varianty', 'tuapse'):
            Category.objects.create(title=slug, slug=slug)
        Brand.objects.create(name='Гостевые дома', slug='guest-houses')

    def test_check_does_not_write_database_or_media(self):
        result = import_item(self.data, self.source)
        self.assertEqual(result['result'], 'check')
        self.assertFalse(Product.objects.exists())
        self.assertFalse(self.target.exists())

    def test_real_fields_map_precision_categories_and_archives(self):
        import_item(self.data, self.source, apply=True)
        obj = Product.objects.get(joomla_id=2425)
        self.assertFalse(obj.is_active)
        self.assertEqual(obj.joomla_source, self.data)
        self.assertEqual(obj.map_coordinates, '38.887676244734415, 44.19781059487658')
        self.assertEqual(obj.map_center, '38.887205,44.196131')
        self.assertEqual(obj.map_zoom, 15)
        self.assertEqual(obj.category.slug, 'vse-varianty')
        self.assertEqual(set(obj.categories.values_list('slug', flat=True)), {'tuapse', 'vse-varianty'})
        self.assertIn('Эконом', obj.rooms_description)
        original = self.data['item']['elements']['e64e1204-0cec-479f-8d6b-7da953d90554']['data']['0']['value']
        self.assertEqual(obj.price_description_source, original)
        parsed = BeautifulSoup(sanitize_prices(obj.price_description), 'html.parser')
        self.assertEqual(len(parsed.find_all('video')), 2)
        self.assertEqual(len(parsed.find_all('iframe')), 1)
        self.assertEqual(len(parsed.find_all('table')), 2)
        for video in parsed.find_all('video'):
            self.assertTrue(video['src'].startswith('/media/jbzoo/2425/'))
        self.assertTrue((self.target / obj.image.name).is_file())

    def test_repeat_does_not_duplicate_or_overwrite_edits(self):
        import_item(self.data, self.source, apply=True)
        Product.objects.update(title='Изменено менеджером')
        result = import_item(self.data, self.source, apply=True)
        self.assertEqual(result['result'], 'unchanged')
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().title, 'Изменено менеджером')

    def test_slug_collision_does_not_overwrite(self):
        Product.objects.create(title='Существующий', slug=self.data['alias'])
        with self.assertRaises(ItemImportError):
            import_item(self.data, self.source, apply=True)
        self.assertEqual(Product.objects.get().title, 'Существующий')
        self.assertFalse(self.target.exists())

    def test_missing_media_or_categories_aborts(self):
        (self.source / self.data['media'][0]['path']).unlink()
        with self.assertRaises(ItemImportError):
            import_item(self.data, self.source, apply=True)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(self.target.exists())

    def test_changed_snapshot_does_not_overwrite(self):
        import_item(self.data, self.source, apply=True)
        changed = copy.deepcopy(self.data)
        changed['item']['name'] = 'Другой снимок'
        with self.assertRaises(ItemImportError):
            import_item(changed, self.source, apply=True)

    def test_private_preview_and_publication_legacy_path(self):
        import_item(self.data, self.source, apply=True)
        obj = Product.objects.get()
        preview = f'/catalog/manage/{obj.pk}/preview/'
        self.assertEqual(self.client.get(obj.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(preview).status_code, 302)
        customer = get_user_model().objects.create_user(username='customer')
        self.client.force_login(customer)
        self.assertEqual(self.client.get(preview).status_code, 302)
        user = get_user_model().objects.create_user(username='manager', password='test')
        user.profile.role = ROLE_MANAGER
        user.profile.save()
        self.client.force_login(user)
        response = self.client.get(preview)
        self.assertEqual(response.status_code, 200, response.get("Location"))
        self.assertIn('private', response['Cache-Control'])
        self.assertContains(response, 'Предпросмотр импорта JBZoo')
        self.assertContains(response, 'Эконом')
        Product.objects.filter(pk=obj.pk).update(is_active=True)
        response = self.client.get('/properties-list/' + obj.slug + '.html')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], obj.get_absolute_url())

    def test_missing_type_is_created_only_on_apply(self):
        Brand.objects.all().delete()
        import_item(self.data, self.source)
        self.assertFalse(Brand.objects.exists())
        import_item(self.data, self.source, apply=True)
        self.assertEqual(Product.objects.get().brand.name, 'Гостевые дома')

    def test_failure_rolls_back_database_and_new_media(self):
        Brand.objects.all().delete()
        with patch.object(Product, 'save', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                import_item(self.data, self.source, apply=True)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(Brand.objects.exists())
        self.assertEqual([p for p in self.target.rglob('*') if p.is_file()], [])

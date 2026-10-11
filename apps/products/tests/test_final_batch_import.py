"""Пустые фото и вторичное фото сохраняются без изменения исходных полей."""
import copy
import json
import tempfile
from pathlib import Path
from PIL import Image
from django.test import TestCase, override_settings
from apps.products.importing.local_batch import read_local_items, import_local_batch
from apps.products.importing.item import ItemImportError
from apps.products.models import Product, Category


class FinalBatchTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'source'
        self.target = Path(self.tmp.name) / 'target'
        self.override = override_settings(MEDIA_ROOT=self.target)
        self.override.enable()
        self.addCleanup(self.override.disable)
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_import_plan.json'
        self.rows = json.loads(fixture.read_text())['batches'][-1]['items']
        for slug in {c for d in self.rows for c in list(d['item']['categories'].values()) + [d['item']['config']['primary_category']]} - {'_root'}:
            Category.objects.create(title=slug, slug=slug)
        for folder, photo in [('user_456', '456u11.jpg'), ('user_606', '606u11.jpg')]:
            directory = self.source / 'images/uploads' / folder
            directory.mkdir(parents=True)
            Image.new('RGB', (10, 10), 'blue').save(directory / photo)
        for name in ['video-2022-04-13-2.mp4', 'video-2022-04-13-3.mp4']:
            (self.source / 'images/uploads/user_606' / name).write_bytes(b'copy fixture')

    def batch(self, rows=None):
        rows = self.rows if rows is None else rows
        return read_local_items(rows, self.source, {d['id']: d['gallery_folder'] for d in rows})

    def test_import_preserves_empty_main_secondary_gallery_state_and_urls(self):
        checked = import_local_batch(self.batch(), self.source)
        self.assertFalse(Product.objects.exists())
        self.assertEqual([r['photos_with_cover'] for r in checked], [0, 1, 0, 0, 1])
        import_local_batch(self.batch(), self.source, apply=True)
        for data in self.rows:
            obj = Product.objects.get(joomla_id=data['id'])
            self.assertEqual(obj.joomla_source['item'], data['item'])
            self.assertEqual(obj.joomla_source['csv'], data['csv'])
            self.assertEqual(obj.is_active, data['item']['state'] == '1')
            self.assertEqual(self.client.get(obj.get_absolute_url()).status_code, 200 if obj.is_active else 404)
        secondary = Product.objects.get(joomla_id=2144)
        self.assertFalse(secondary.image)
        photo = secondary.gallery.get().image
        self.assertEqual((self.target / photo.name).read_bytes(), (self.source / 'images/uploads/user_456/456u11.jpg').read_bytes())
        self.assertTrue(all(r['result'] == 'unchanged' for r in import_local_batch(self.batch(), self.source, apply=True)))

    def test_without_media_cannot_hide_existing_media(self):
        for name, field, value in [('Главное Фото', 'file', 'images/uploads/user_1/a.jpg'), ('Фото:', 'file', 'images/uploads/user_1/b.jpg'), ('Цены', 'value', '<video src="images/uploads/user_1/a.mp4"></video>')]:
            row = copy.deepcopy(self.rows[0])
            element = next(e for e in row['item']['elements'].values() if e['name'].strip() == name)
            element['data']['0'][field] = value
            with self.subTest(name=name), self.assertRaises(ItemImportError):
                self.batch([row])
        self.assertFalse(Product.objects.exists())

    def test_missing_secondary_file_aborts_entire_batch(self):
        (self.source / 'images/uploads/user_456/456u11.jpg').unlink()
        with self.assertRaises(ItemImportError):
            self.batch()
        self.assertFalse(Product.objects.exists())
        self.assertFalse(self.target.exists())

    def test_shared_folder_does_not_merge_distinct_joomla_ids(self):
        old = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_orion_2425.json').read_text())
        self.assertNotEqual(old['alias'], self.rows[-1]['alias'])
        import_local_batch(self.batch([self.rows[-1]]), self.source, apply=True)
        old['gallery_folder'] = 'user_606'
        old['legacy_prefix'] = old['url'].split('/')[-2]
        old_batch = read_local_items([old], self.source, {2425: 'user_606'})
        import_local_batch(old_batch, self.source, apply=True)
        self.assertEqual(Product.objects.count(), 2)
        self.assertNotEqual(Product.objects.get(joomla_id=1806).image.name, Product.objects.get(joomla_id=2425).image.name)

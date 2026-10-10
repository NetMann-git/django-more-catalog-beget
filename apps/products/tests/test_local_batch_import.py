"""Реальные три карточки и локальные фотографии без заранее заданных хешей."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.test import TestCase, override_settings

from apps.products.importing.item import ItemImportError
from apps.products.importing.local_batch import read_local_batch, import_local_batch
from apps.products.models import Product, Category, ProductGalleryImage


class LocalBatchTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.target = self.root / 'target'
        self.override = override_settings(MEDIA_ROOT=self.target)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.fixture = Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_trial_three.json'
        self.raw = json.loads(self.fixture.read_text())
        categories = {c for row in self.raw for c in list(row['item']['categories'].values()) + [row['item']['config']['primary_category']]}
        for c in categories:
            Category.objects.create(title=c, slug=c)
        for row in self.raw:
            cover = next(e['data']['0']['file'] for e in row['item']['elements'].values() if e['name']=='Главное Фото')
            directory = self.source / Path(cover).parent
            directory.mkdir(parents=True)
            for name in [Path(cover).name, 'photo2.jpg', 'photo10.jpg']:
                Image.new('RGB', (10,10), 'blue').save(directory/name)

    def batch(self):
        return read_local_batch(self.fixture, self.source)

    def test_check_and_real_values(self):
        rows = import_local_batch(self.batch(), self.source)
        self.assertEqual(len(rows), 3)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual([r['gallery_photos'] for r in rows], [2,2,2])

    def test_apply_natural_order_long_alias_and_legacy_urls(self):
        import_local_batch(self.batch(), self.source, apply=True)
        self.assertEqual(Product.objects.count(), 3)
        self.assertEqual(ProductGalleryImage.objects.count(), 6)
        for row in self.raw:
            obj = Product.objects.get(joomla_id=row['id'])
            self.assertEqual(obj.slug, row['alias'])
            self.assertEqual(obj.joomla_source['item'], row['item'])
            self.assertEqual([Path(g.image.name).name for g in obj.gallery.all()], ['photo2.jpg','photo10.jpg'])
            self.assertEqual(obj.is_active, row['item']['state']=='1')
            self.assertTrue((self.target/obj.image.name).exists())
            response = self.client.get('/'+row['legacy_prefix']+'/'+row['alias']+'.html')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(obj.get_absolute_url(), '/' + row['legacy_prefix'] + '/' + row['alias'] + '.html')
            moved = self.client.get('/catalog/' + obj.slug + '/')
            self.assertEqual(moved.status_code, 301)
            self.assertEqual(moved['Location'], obj.get_absolute_url())
        flat = Product.objects.get(joomla_id=1963)
        self.assertGreater(len(flat.slug), 50)
        self.assertEqual(flat.map_coordinates, '39.70474499999996,43.6450220745537')
        self.assertEqual(Product.objects.get(joomla_id=1096).categories.count(), 6)

    def test_repeat_does_not_overwrite_manual_edits(self):
        import_local_batch(self.batch(), self.source, apply=True)
        Product.objects.filter(joomla_id=1096).update(title='Правка менеджера')
        result = import_local_batch(self.batch(), self.source, apply=True)
        self.assertTrue(all(r['result']=='unchanged' for r in result))
        self.assertEqual(ProductGalleryImage.objects.count(),6)
        self.assertEqual(Product.objects.get(joomla_id=1096).title,'Правка менеджера')

    def test_missing_folder_or_cover_aborts(self):
        cover = next(e['data']['0']['file'] for e in self.raw[-1]['item']['elements'].values() if e['name']=='Главное Фото')
        (self.source/cover).unlink()
        with self.assertRaises(ItemImportError):self.batch()
        self.assertFalse(Product.objects.exists())

    def test_changed_local_photos_aborts_repeat(self):
        import_local_batch(self.batch(), self.source, apply=True)
        Image.new('RGB',(11,11),'red').save(self.source/'images/uploads/user_396/photo2.jpg')
        with self.assertRaises(ItemImportError):
            import_local_batch(self.batch(), self.source, apply=True)
        self.assertEqual(Product.objects.count(),3)

    def test_second_object_failure_rolls_back_whole_group_and_media(self):
        actual_save = Product.save
        def fail(obj,*args,**kwargs):
            if obj.joomla_id==1963:raise RuntimeError('write failed')
            return actual_save(obj,*args,**kwargs)
        with patch.object(Product,'save',fail):
            with self.assertRaises(RuntimeError):
                import_local_batch(self.batch(),self.source,apply=True)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(ProductGalleryImage.objects.exists())
        self.assertEqual([f for f in self.target.rglob('*') if f.is_file()],[])

    def test_unicode_names_uppercase_extension_and_local_report(self):
        folder = self.source/'images/uploads/user_396'
        (folder/'photo2.jpg').rename(folder/'Фото2.JPG')
        (folder/'ADD_PHOTOS_HERE.txt').write_text('placeholder')
        batch = self.batch()
        report = import_local_batch(batch, self.source, apply=True)
        self.assertIn('ADD_PHOTOS_HERE.txt',report[0]['ignored'])
        self.assertTrue(Product.objects.get(joomla_id=1096).gallery.filter(image__endswith='Фото2.JPG').exists())

    def test_virtual_root_is_archived_without_creating_a_category(self):
        batch = self.batch()
        item = batch[0][0]
        item['item']['categories']['extra'] = '_root'
        import_local_batch(batch, self.source, apply=True)
        obj = Product.objects.get(joomla_id=item['id'])
        self.assertIn('_root', obj.joomla_source['item']['categories'].values())
        self.assertFalse(obj.categories.filter(slug='_root').exists())
        self.assertEqual(obj.category.slug, item['item']['config']['primary_category'])

    def test_mini_hotels_create_their_own_type_and_keep_source(self):
        batch = self.batch()
        for element in batch[0][0]['item']['elements'].values():
            if element['name'] == 'Тип жилья':
                element['data']['0']['list-0'] = 'Мини Гостиницы'
        import_local_batch(batch, self.source, apply=True)
        obj = Product.objects.get(joomla_id=batch[0][0]['id'])
        self.assertEqual(obj.brand.name, 'Мини Гостиницы')
        self.assertEqual(obj.brand.slug, 'mini-gostinitsy')
        self.assertEqual(obj.joomla_source['item'], batch[0][0]['item'])
        self.assertTrue(all(row['result'] == 'unchanged' for row in import_local_batch(batch, self.source, apply=True)))

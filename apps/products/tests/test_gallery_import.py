"""Порядок, повторный запуск и атомарность импорта галереи."""
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.test import TestCase, override_settings

from apps.products.importing.gallery import filename_order, import_gallery, read_images, read_manifest
from apps.products.importing.item import ItemImportError
from apps.products.models import Product, ProductGalleryImage


class GalleryImportTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = override_settings(MEDIA_ROOT=self.root / 'media')
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        names = ['606u11.jpg', '606u12.jpg', '606u20.jpg', '606u100.jpg']
        self.blobs = {}
        for i, name in enumerate(names):
            output = io.BytesIO()
            Image.new('RGB', (8, 8), (20*i, 40, 50)).save(output, format='JPEG')
            self.blobs[name] = output.getvalue()
        self.manifest = {'schema':1, 'joomla_id':2425, 'alias':'orion', 'folder':'user_606',
                         'cover':'606u11.jpg', 'images':[{'name':name, 'size':len(blob),
                         'sha256':hashlib.sha256(blob).hexdigest()} for name, blob in self.blobs.items()]}
        self.product = Product.objects.create(title='Орион', slug='orion', joomla_id=2425,
            image='jbzoo/2425/images/uploads/user_606/606u11.jpg', is_active=False,
            joomla_source={'item':{'elements':{'gallery':{'name':'Галерея','data':{'value':'user_606'}}}}})

    def test_natural_order_uses_numbers(self):
        self.assertEqual(sorted(['photo10.jpg','photo2.jpg','photo1.jpg'], key=filename_order),
                         ['photo1.jpg','photo2.jpg','photo10.jpg'])

    def test_check_writes_nothing(self):
        result = import_gallery(self.manifest, self.blobs)
        self.assertEqual(result['new_records'], 3)
        self.assertFalse(self.product.gallery.exists())
        self.assertFalse((self.root / 'media').exists())

    def test_apply_cover_excluded_and_repeat_keeps_edits(self):
        import_gallery(self.manifest, self.blobs, apply=True)
        gallery = list(self.product.gallery.all())
        self.assertEqual([Path(row.image.name).name for row in gallery], ['606u12.jpg','606u20.jpg','606u100.jpg'])
        self.assertEqual([row.sort_order for row in gallery], [0,1,2])
        for row in gallery:
            self.assertTrue((self.root / 'media' / row.image.name).is_file())
        gallery[0].alt = 'Правка менеджера'
        gallery[0].sort_order = 90
        gallery[0].save()
        result = import_gallery(self.manifest, self.blobs, apply=True)
        self.assertEqual(result['new_records'], 0)
        self.assertEqual(result['new_files'], 0)
        self.assertEqual(self.product.gallery.count(), 3)
        gallery[0].refresh_from_db()
        self.assertEqual(gallery[0].alt, 'Правка менеджера')
        self.assertEqual(gallery[0].sort_order, 90)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertEqual(self.product.joomla_source['item']['elements']['gallery']['data']['value'], 'user_606')

    def test_manual_gallery_records_not_overwritten(self):
        manual = ProductGalleryImage.objects.create(product=self.product, image='manual.jpg', sort_order=5, alt='Своя фотография')
        import_gallery(self.manifest, self.blobs, apply=True)
        self.assertEqual(list(self.product.gallery.values_list('sort_order', flat=True)), [5,6,7,8])
        manual.refresh_from_db()
        self.assertEqual(manual.alt, 'Своя фотография')

    def test_database_failure_removes_only_new_files(self):
        existing = self.root / 'media/jbzoo/2425/images/uploads/user_606/606u12.jpg'
        existing.parent.mkdir(parents=True)
        existing.write_bytes(self.blobs['606u12.jpg'])
        real_create = ProductGalleryImage.objects.create
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise RuntimeError('database write failed')
            return real_create(**kwargs)
        with patch.object(ProductGalleryImage.objects, 'create', side_effect=create):
            with self.assertRaises(RuntimeError):
                import_gallery(self.manifest, self.blobs, apply=True)
        self.assertFalse(self.product.gallery.exists())
        self.assertEqual([p.name for p in (self.root/'media').rglob('*') if p.is_file()], ['606u12.jpg'])

    def test_media_collision_or_wrong_object_aborts(self):
        file = self.root / 'media/jbzoo/2425/images/uploads/user_606/606u12.jpg'
        file.parent.mkdir(parents=True)
        file.write_bytes(b'other image')
        with self.assertRaises(ItemImportError):
            import_gallery(self.manifest, self.blobs, apply=True)
        self.assertFalse(self.product.gallery.exists())
        self.product.slug = 'changed'
        self.product.save()
        with self.assertRaises(ItemImportError):
            import_gallery(self.manifest, self.blobs, apply=True)

    def test_zip_and_directory_validation_and_hash(self):
        archive = self.root / 'gallery.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name, blob in self.blobs.items():
                z.writestr('user_606/'+name, blob)
        self.assertEqual(read_images(archive, self.manifest), self.blobs)
        folder = self.root / 'user_606'
        folder.mkdir()
        for name, blob in self.blobs.items():
            (folder / name).write_bytes(blob)
        self.assertEqual(read_images(folder, self.manifest), self.blobs)
        (folder / '606u12.jpg').write_bytes(b'changed')
        with self.assertRaises(ItemImportError):
            read_images(folder, self.manifest)
        with zipfile.ZipFile(archive, 'a') as z:
            z.writestr('../unexpected.jpg', b'x')
        with self.assertRaises(ItemImportError):
            read_images(archive, self.manifest)

    def test_manifest_and_real_fixture(self):
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_orion_2425_gallery.json'
        actual = read_manifest(fixture)
        self.assertEqual(len(actual['images']), 66)
        self.assertEqual(actual['images'][0]['name'], '606u11.jpg')
        self.assertEqual(actual['images'][-1]['name'], '606u76.jpg')
        path = self.root / 'manifest.json'
        invalid = dict(self.manifest, images=list(reversed(self.manifest['images'])))
        path.write_text(json.dumps(invalid))
        with self.assertRaises(ItemImportError):
            read_manifest(path)

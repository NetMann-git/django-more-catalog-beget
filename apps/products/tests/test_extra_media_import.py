"""Дополнительные иллюстрации копируются точно и не становятся фото галереи."""
import json
import tempfile
from pathlib import Path

from PIL import Image
from django.test import TestCase, override_settings

from apps.products.importing.item import FIELDS, ItemImportError
from apps.products.importing.local_batch import read_local_items, import_local_batch
from apps.products.importing.media_paths import EXTRA_MEDIA
from apps.products.models import Product, Category


class ExtraMediaTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / 'source'
        self.target = root / 'target'
        override = override_settings(MEDIA_ROOT=self.target)
        override.enable()
        self.addCleanup(override.disable)
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/jbzoo_import_plan.json'
        plan = json.loads(fixture.read_text())
        self.rows = [d for b in plan['batches'] for d in b['items'] if d['id'] in EXTRA_MEDIA]
        self.assertEqual(len(self.rows), 3)
        self.approved = {d['id']: d['gallery_folder'] for d in self.rows}
        categories = {c for d in self.rows for c in list(d['item']['categories'].values()) + [d['item']['config']['primary_category']] if c != '_root'}
        for c in categories:
            Category.objects.create(title=c, slug=c)
        for d in self.rows:
            cover = next(e['data']['0']['file'] for e in d['item']['elements'].values() if e['name'] == 'Главное Фото')
            directory = self.source / Path(cover).parent
            directory.mkdir(parents=True)
            for name in [Path(cover).name, 'photo2.jpg', 'photo10.jpg']:
                Image.new('RGB', (10, 10), 'blue').save(directory / name)
            for rel in EXTRA_MEDIA[d['id']]:
                file = self.source / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                Image.new('RGB', (10, 10), 'red').save(file)

    def batch(self):
        return read_local_items(self.rows, self.source, self.approved)

    def test_exact_bytes_html_references_and_gallery_exclusion(self):
        batch = self.batch()
        import_local_batch(batch, self.source, apply=True)
        for d, _ in batch:
            obj = Product.objects.get(joomla_id=d['id'])
            self.assertEqual(obj.joomla_source['item'], d['item'])
            self.assertEqual([Path(g.image.name).name for g in obj.gallery.all()], ['photo2.jpg', 'photo10.jpg'])
            content = '\n'.join(getattr(obj, field) for field in FIELDS.values())
            for rel in EXTRA_MEDIA[d['id']]:
                self.assertEqual((self.target / 'jbzoo' / str(d['id']) / rel).read_bytes(), (self.source / rel).read_bytes())
                self.assertIn('/jbzoo/' + str(d['id']) + '/' + rel, content)
        self.assertTrue(all(r['result'] == 'unchanged' for r in import_local_batch(batch, self.source, apply=True)))

    def test_unreviewed_external_file_is_rejected_before_write(self):
        for element in self.rows[0]['item']['elements'].values():
            if element['name'].strip() == 'Коротко':
                element['data']['0']['value'] += '<img src="images/stories/not-reviewed.jpg">'
        with self.assertRaises(ItemImportError):
            self.batch()
        self.assertFalse(Product.objects.exists())
        self.assertFalse(self.target.exists())

    def test_corrupt_extra_image_is_rejected_before_write(self):
        (self.source / 'images/stories/gagra.jpg').write_bytes(b'broken')
        with self.assertRaises(ItemImportError):
            self.batch()
        self.assertFalse(Product.objects.exists())
        self.assertFalse(self.target.exists())

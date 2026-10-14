import io
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from .models import InformationMaterial
from .media import media_plan, legacy_media_path, file_hash


class InformationMediaTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.settings = override_settings(BASE_DIR=self.root, MEDIA_ROOT=self.root/'media')
        self.settings.enable();self.addCleanup(self.settings.disable)
        self.obj = InformationMaterial.objects.create(joomla_id=10000,kind='info',title='Материал',slug='article',is_active=True,image_source='images/cover.jpg|||Подпись',body='<img src="images/inline.png">')
        for path, data in [('images/cover.jpg',b'original-jpeg-bytes'),('images/inline.png',b'original-png-bytes')]:
            file=self.source/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)

    def run_import(self, **kwargs):
        call_command('import_information_media',source=str(self.source),stdout=io.StringIO(),**kwargs)

    def test_copy_is_identical_and_repeat_skips(self):
        self.run_import(apply=True)
        for relative in ['images/cover.jpg','images/inline.png']:
            target=self.root/'media/joomla-information'/relative
            self.assertEqual(target.read_bytes(),(self.source/relative).read_bytes())
            self.assertEqual(file_hash(target),file_hash(self.source/relative))
        self.run_import(apply=True)
        plan=media_plan([self.obj],self.source)
        self.assertEqual(plan['already_identical'],2)
        self.obj.refresh_from_db();self.assertEqual(self.obj.image_source,'images/cover.jpg|||Подпись')
        self.assertEqual(len(list((self.root/'patch-backups').glob('*.json'))),2)

    def test_conflict_stops_before_copy(self):
        target=self.root/'media/joomla-information/images/cover.jpg'
        target.parent.mkdir(parents=True);target.write_bytes(b'different-existing-file')
        with self.assertRaises(CommandError):self.run_import(apply=True)
        self.assertEqual(target.read_bytes(),b'different-existing-file')
        self.assertFalse((target.parent/'inline.png').exists())

    def test_missing_requires_explicit_partial_import(self):
        (self.source/'images/inline.png').unlink()
        self.run_import(check=True)
        with self.assertRaises(CommandError):self.run_import(apply=True)
        self.assertFalse((self.root/'media/joomla-information/images/cover.jpg').exists())
        self.run_import(apply=True,allow_missing=True)
        self.assertTrue((self.root/'media/joomla-information/images/cover.jpg').exists())

    def test_rendering_uses_original_cover_and_inline(self):
        self.run_import(apply=True)
        response=self.client.get(self.obj.get_absolute_url())
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'/media/joomla-information/images/cover.jpg')
        self.assertContains(response,'/media/joomla-information/images/inline.png')
        self.assertNotContains(response,'Изображение пока недоступно.')
        self.obj.refresh_from_db();self.assertEqual(self.obj.body,'<img src="images/inline.png">')

    def test_unsafe_paths_and_symlink_escape(self):
        for path in ['images/../outside.jpg','images/%2e%2e/outside.jpg','https://example.com/images/x.jpg','images/x.php']:
            self.assertIsNone(legacy_media_path(path))
        outside=self.root/'outside.jpg';outside.write_bytes(b'private')
        (self.source/'images/cover.jpg').unlink()
        (self.source/'images/cover.jpg').symlink_to(outside)
        with self.assertRaises(CommandError):self.run_import(apply=True)

    def test_known_absent_media_are_not_required(self):
        from .media import EXCLUDED_MEDIA, material_paths
        self.assertEqual(len(EXCLUDED_MEDIA),34)
        self.obj.body += ''.join(f'<img src="{path}">' for path in EXCLUDED_MEDIA)
        self.obj.save()
        paths=material_paths(self.obj)
        self.assertFalse(paths & EXCLUDED_MEDIA)
        self.run_import(apply=True)
        self.obj.refresh_from_db()
        self.assertIn('images/camera/mor-vokzal.jpg',self.obj.body)

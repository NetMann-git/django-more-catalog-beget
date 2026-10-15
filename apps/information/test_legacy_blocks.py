import io
import json
import tempfile
from pathlib import Path
from django.conf import settings
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase
from apps.products.management.commands.audit_housing_site import read_only
from .legacy_blocks import legacy_blocks, audit_information_blocks
from .models import InformationMaterial
from .rendering import material_html


class LegacyBlocksAuditTests(TestCase):
    def setUp(self):
        self.public = InformationMaterial.objects.create(title='Публичный', slug='blocks-public', kind='info', is_active=True,
            intro='{module 117}', body='{module 117}{module 117}{loadmodule mod_menu,Меню}',
            extra_body='{module 220|style}', html_insert='{loadposition footer}{modal example.html}Текст{/modal}', source={'archive': '{module 999}'})
        self.hidden = InformationMaterial.objects.create(title='Скрытый', slug='blocks-hidden', kind='map', body='{module 284}', is_active=False)

    def test_duplicates_fields_grouping_and_no_source_archive_scanning(self):
        before = list(InformationMaterial.objects.values())
        with connection.execute_wrapper(read_only):
            report = audit_information_blocks()
        self.assertEqual(report['materials_checked'], 1)
        self.assertEqual(report['affected_materials'], 1)
        self.assertEqual(report['occurrences'], 7)
        self.assertEqual(report['numeric_module_ids'], [117, 220])
        self.assertEqual(report['unresolved_blocks'], 5)
        self.assertEqual(report['by_kind'], {'loadmodule': 1, 'loadposition': 1, 'modal': 1, 'module': 4})
        group = next(row for row in report['blocks'] if row['module_id'] == 117)
        self.assertEqual(group['occurrences'], 3)
        self.assertEqual(group['materials_count'], 1)
        material = report['materials'][0]
        self.assertEqual({row['field'] for row in material['blocks']}, {'intro','body','extra_body','html_insert'})
        self.assertIn('/admin/information/informationmaterial/', material['admin_url'])
        self.assertFalse(report['ok'])
        self.assertEqual(list(InformationMaterial.objects.values()), before)

    def test_unpublished_is_opt_in(self):
        report = audit_information_blocks(include_unpublished=True)
        self.assertEqual(report['materials_checked'], 2)
        self.assertEqual(report['published_materials_checked'], 1)
        self.assertEqual(report['affected_published_materials'], 1)
        self.assertEqual(report['affected_materials'], 2)
        self.assertEqual(report['numeric_module_ids'], [117,220,284])
        hidden_group = next(row for row in report['blocks'] if row['module_id'] == 284)
        self.assertEqual(hidden_group['published_materials_count'], 0)

    def test_token_parsing_matches_rendering_without_executing(self):
        value = '{MODULE 00117|style}{loadmodule mod_login,Login}{loadposition footer}{modal example.html}Ссылка{/modal}{source}Текст{/source}{tab Фото}{/tabs}'
        blocks = list(legacy_blocks(value))
        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[0]['module_id'], 117)
        self.assertTrue(all(row['module_id'] is None for row in blocks[1:]))
        html = material_html(value)
        self.assertEqual(html.count('Этот дополнительный блок пока недоступен.'), 4)
        self.assertNotIn('{/modal}', html)
        self.assertEqual(list(legacy_blocks('{module '+ '9'*5000+'}'))[0]['module_id'], None)

    def test_clean_materials_are_complete_and_unknown_named_module_is_retained(self):
        self.public.intro = self.public.extra_body = self.public.html_insert = ''
        self.public.body = 'Обычный текст {tabs}{tab Фото}{/tabs}'
        self.public.save()
        self.assertTrue(audit_information_blocks()['ok'])
        self.public.body = '{module Название блока}'
        self.public.save()
        report = audit_information_blocks()
        self.assertIsNone(report['blocks'][0]['module_id'])
        self.assertEqual(report['blocks'][0]['arguments'], ['Название блока'])

    def test_command_default_and_strict_save_reports_without_modification(self):
        root = Path(settings.BASE_DIR) / 'patch-backups'
        root.mkdir(exist_ok=True)
        before = list(InformationMaterial.objects.values())
        with tempfile.TemporaryDirectory(dir=root) as directory:
            output = Path(directory) / 'blocks.json'
            call_command('audit_information_blocks', output=str(output), stdout=io.StringIO())
            self.assertFalse(json.loads(output.read_text(encoding='utf-8'))['ok'])
            with self.assertRaises(CommandError):
                call_command('audit_information_blocks', output=str(output), fail_on_unresolved=True, include_unpublished=True, stdout=io.StringIO())
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['materials_checked'], 2)
        self.assertEqual(list(InformationMaterial.objects.values()), before)

    def test_report_cannot_be_written_outside_backup_directory(self):
        with self.assertRaisesMessage(CommandError, 'patch-backups'):
            call_command('audit_information_blocks', output=str(Path(settings.BASE_DIR) / 'outside-block-report.json'), stdout=io.StringIO())

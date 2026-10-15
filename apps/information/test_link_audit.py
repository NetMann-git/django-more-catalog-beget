import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from apps.products.management.commands.audit_housing_site import read_only
from .link_audit import audit_information_links, check_target, internal_target
from .models import InformationMaterial


@override_settings(ALLOWED_HOSTS=['audit.local'], SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class InformationLinkAuditTests(TestCase):
    def setUp(self):
        self.target = InformationMaterial.objects.create(title='Цель', slug='audit-target', kind='info', is_active=True)
        self.hidden = InformationMaterial.objects.create(title='Скрытый', slug='audit-hidden', kind='info')
        self.source = InformationMaterial.objects.create(title='Источник', slug='audit-source', kind='info', is_active=True,
            body='<p>Исходник</p>', source={'raw': 'keep'})

    def test_internal_hosts_relative_paths_queries_and_skips(self):
        for host in ['дикарь-сочи.рф', 'www.дикарь-сочи.рф', 'дикарь-сочи.рф'.encode('idna').decode()]:
            self.assertEqual(internal_target('https://'+host+'/information/?page=2#top', '/base.html'), ('/information/?page=2', None))
        self.assertEqual(internal_target('../maps/', '/information/material/one/'), ('/information/material/maps/', None))
        self.assertEqual(internal_target('//example.com/test', '/'), (None, 'external'))
        self.assertEqual(internal_target('https://дикарь-сочи.рф.evil.test/', '/'), (None, 'external'))
        self.assertEqual(internal_target('mailto:a@example.com', '/'), (None, 'other_protocol'))
        self.assertEqual(internal_target('#price', '/'), (None, 'fragment_or_empty'))
        self.assertEqual(internal_target('/media/photo.jpg', '/'), (None, 'media_or_static'))
        self.assertEqual(internal_target('https://[bad', '/'), (None, 'invalid_url'))

    def test_live_missing_and_hidden_links_are_reported_without_changes(self):
        self.source.body = '<a href="{0}">Цель</a><a href="{0}">Ещё раз</a><a href="{1}">Скрытый</a><a href="/missing-old-page.html">Старая</a><a href="https://example.com/">Внешняя</a>'.format(self.target.get_absolute_url(), self.hidden.get_absolute_url())
        self.source.save()
        before = list(InformationMaterial.objects.values())
        with connection.execute_wrapper(read_only):
            report = audit_information_links()
        self.assertEqual(report['published_materials'], 2)
        self.assertEqual(report['internal_targets_checked'], 3)
        self.assertEqual(report['skipped_counts'], {'external': 1})
        self.assertEqual(len(report['issues']), 2)
        self.assertFalse(report['ok'])
        self.assertEqual({r['problem'] for r in report['issues']}, {'missing_route', 'http_status'})
        self.assertTrue(all(r['material_id'] == self.source.pk and r['field'] == 'body' and r['admin_url'] for r in report['issues']))
        self.assertEqual(list(InformationMaterial.objects.values()), before)

    def test_links_removed_by_safe_rendering_are_not_silently_ignored(self):
        self.source.body = '<a href="http://дикарь-сочи.рф/old.html">Старая HTTP-ссылка</a><a href="images/missing.jpg">Медиа</a>'
        self.source.save()
        with patch('apps.information.link_audit.Client.get', side_effect=AssertionError('Must not request')) as get:
            report = audit_information_links()
        get.assert_not_called()
        self.assertFalse(report['ok'])
        self.assertEqual(len(report['issues']), 1)
        self.assertEqual(report['issues'][0]['problem'], 'link_not_rendered')
        self.assertEqual(report['issues'][0]['href'], 'http://дикарь-сочи.рф/old.html')
        self.source.refresh_from_db()
        self.assertIn('http://дикарь-сочи.рф/old.html', self.source.body)

    def test_public_alias_redirect_is_followed_and_listed(self):
        self.target.joomla_id = 409
        self.target.save()
        alias = reverse('information:material', args=[self.target.slug])
        self.source.body = '<a href="'+alias+'">Ссылка</a>'
        self.source.save()
        report = audit_information_links()
        self.assertTrue(report['ok'])
        self.assertEqual(len(report['redirected_links']), 1)
        self.assertEqual(report['redirected_links'][0]['target'], '/aeroekspress.html')

    def test_actions_admin_and_external_are_never_requested(self):
        self.source.body = '<a href="/catalog/delete/123/">Удаление</a><a href="/admin/">Админка</a><a href="https://example.com/">Внешняя</a>'
        self.source.save()
        with patch('apps.information.link_audit.Client.get', side_effect=AssertionError('Must not request')) as get:
            report = audit_information_links()
        get.assert_not_called()
        self.assertTrue(report['ok'])
        self.assertEqual(len(report['unchecked_links']), 2)
        self.assertEqual(report['skipped_counts']['external'], 1)

    def test_duplicate_targets_are_fetched_once_across_fields(self):
        link = '<a href="'+self.target.get_absolute_url()+'">Цель</a>'
        self.source.body = link
        self.source.intro = link
        self.source.save()
        client = Client(HTTP_HOST='audit.local')
        with patch('apps.information.link_audit.Client.get', side_effect=client.get) as get:
            report = audit_information_links()
        self.assertEqual(get.call_count, 1)
        self.assertEqual(report['internal_targets_checked'], 1)
        self.assertTrue(report['ok'])

    def test_redirect_loop_and_external_redirect_are_bounded(self):
        from django.http import HttpResponseRedirect
        client = Client()
        target = self.target.get_absolute_url()
        with patch.object(client, 'get', return_value=HttpResponseRedirect(target)):
            self.assertEqual(check_target(client, target)['problem'], 'redirect_loop')
        with patch.object(client, 'get', return_value=HttpResponseRedirect('https://example.com/')) as get:
            self.assertEqual(check_target(client, target)['skipped'], 'redirect_external')
            self.assertEqual(get.call_count, 1)

    def test_report_written_before_failure_and_output_is_confined(self):
        root = Path(settings.BASE_DIR) / 'patch-backups'
        root.mkdir(exist_ok=True)
        self.source.body = '<a href="/missing.html">Нет страницы</a>'
        self.source.save()
        with tempfile.TemporaryDirectory(dir=root) as directory:
            output = Path(directory) / 'report.json'
            with self.assertRaises(CommandError):
                call_command('audit_information_links', output=str(output), stdout=io.StringIO())
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertFalse(report['ok'])
            self.assertEqual(len(report['issues']), 1)
        with self.assertRaisesMessage(CommandError, 'patch-backups'):
            call_command('audit_information_links', output=str(root.parent / 'outside-report.json'), stdout=io.StringIO())

import io
import json
from urllib.parse import urlsplit
from xml.etree.ElementTree import fromstring
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import InformationCategory, InformationMaterial


class InformationSitemapTests(TestCase):
    def paths(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        urls = [node.text for node in fromstring(response.content).findall('{*}url/{*}loc')]
        self.assertEqual(len(urls), len(set(urls)))
        return {urlsplit(url).path for url in urls}

    def test_legacy_material_and_published_categories(self):
        category = InformationCategory.objects.create(joomla_id=1, title='Статьи', slug='articles')
        material = InformationMaterial.objects.create(joomla_id=22, kind='info', title='Водопады', slug='waterfalls', is_active=True, body='<p>Текст</p>')
        paths = self.paths()
        for path in ['/information/', '/information/maps/', material.get_absolute_url(), reverse('information:category', args=[category.slug])]:
            self.assertIn(path, paths)
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertNotIn(reverse('information:material', args=[material.slug]), paths)
        material.is_active = False
        material.save()
        self.assertNotIn(material.get_absolute_url(), self.paths())

    def test_hidden_ancestors_excluded(self):
        hidden = InformationCategory.objects.create(joomla_id=1, title='Скрытая', slug='hidden', is_published=False)
        child = InformationCategory.objects.create(joomla_id=2, title='Дочерняя', slug='child', parent=hidden)
        for category in [hidden, child]:
            self.assertNotIn(reverse('information:category', args=[category.slug]), self.paths())

    def test_site_audit_checks_information_without_writes(self):
        material = InformationMaterial.objects.create(joomla_id=22, kind='info', title='Водопады', slug='waterfalls', is_active=True, body='<p>Исходный текст</p>')
        output = io.StringIO()
        call_command('audit_housing_site', stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report['ok'])
        self.assertEqual(report['published_information_materials'], 1)
        self.assertEqual(report['published_objects'], 0)
        self.assertEqual(report['public_pages_checked'], 6)
        material.refresh_from_db()
        self.assertEqual(material.body, '<p>Исходный текст</p>')

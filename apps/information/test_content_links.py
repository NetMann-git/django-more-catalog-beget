from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse
from .content_links import normalize_content_link, REVIEW_PATH
from .link_audit import audit_information_links
from .models import InformationMaterial
from .rendering import material_html


class LegacyContentLinkTests(TestCase):
    def test_relative_map_and_activity_links_resolve_from_site_root(self):
        for href in ['karta-sochi/abkhaziya.html', 'razvlecheniya/117-kajtserfing.html']:
            with self.subTest(href=href):
                soup = BeautifulSoup(material_html('<a href="'+href+'">Перейти</a>'), 'html.parser')
                self.assertEqual(soup.a['href'], '/'+href)
        self.assertEqual(normalize_content_link('karta-sochi.html'), reverse('information:maps'))
        self.assertEqual(normalize_content_link('otzyvy-ob-otdyxe-v-sochi-adlere.html'), REVIEW_PATH)

    def test_own_domain_becomes_local_including_http_www_punycode(self):
        for host in ['дикарь-сочи.рф', 'www.дикарь-сочи.рф', 'дикарь-сочи.рф'.encode('idna').decode()]:
            for prefix in ['http://', 'https://', '//']:
                self.assertEqual(normalize_content_link(prefix+host+'/'), '/')
                self.assertEqual(normalize_content_link(prefix+host+'/karta-sochi/abkhaziya.html?q=1#map'), '/karta-sochi/abkhaziya.html?q=1#map')

    def test_unknown_and_unsafe_links_are_not_promoted(self):
        for href in ['javascript:alert(1)', 'data:text/html,test', 'http://example.com/',
                     'http://дикарь-сочи.рф.evil.test/', 'http://user@дикарь-сочи.рф/',
                     'http://дикарь-сочи.рф:8080/', '../karta-sochi/abkhaziya.html',
                     'unknown/path.html', 'http://дикарь-сочи.рф/unknown.html',
                     'karta-sochi\\abkhaziya.html', 'https://[bad']:
            with self.subTest(href=href):
                self.assertEqual(normalize_content_link(href), href)
                soup = BeautifulSoup(material_html('<a href="'+href+'">Текст</a>'), 'html.parser')
                self.assertFalse(soup.a.has_attr('href'))
        external = 'https://example.com/test'
        self.assertEqual(normalize_content_link(external), external)
        self.assertEqual(BeautifulSoup(material_html('<a href="'+external+'">Внешняя</a>'), 'html.parser').a['href'], external)

    def test_encoded_joomla_source_is_sanitized_after_normalization(self):
        html = material_html('{source}<span>&lt;a href="karta-sochi.html" onclick="alert(1)"&gt;Карта&lt;/a&gt;&lt;script&gt;alert(1)&lt;/script&gt;</span>{/source}')
        soup = BeautifulSoup(html, 'html.parser')
        self.assertEqual(soup.a['href'], reverse('information:maps'))
        self.assertNotIn('onclick', html)
        self.assertIsNone(soup.script)

    def test_render_and_audit_keep_source_and_validate_destination(self):
        destination = InformationMaterial.objects.create(joomla_id=99, title='Кайтсерфинг', slug='kait', kind='info', is_active=True)
        original = '<a href="razvlecheniya/117-kajtserfing.html">Кайтсерфинг</a>'
        material = InformationMaterial.objects.create(title='Материал', slug='content-links-source', kind='info', is_active=True, body=original, source={'raw': original})
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=['audit.local']):
            report = audit_information_links()
        self.assertTrue(report['ok'], report['issues'])
        self.assertEqual(report['internal_targets_checked'], 1)
        material.refresh_from_db()
        self.assertEqual(material.body, original)
        self.assertEqual(material.source, {'raw': original})
        self.assertContains(self.client.get(material.get_absolute_url()), 'href="'+destination.get_absolute_url()+'"')

"""Проверка публичных адресов и SEO без записи в базу и создания миниатюр."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit
from xml.etree.ElementTree import fromstring

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import Client, override_settings
from django.urls import reverse

from apps.information.models import InformationMaterial
from apps.information.sitemap import public_information_paths
from apps.products.category_views import public_tree
from apps.products.models import Brand, Product


def read_only(execute, sql, params, many, context):
    if not sql.lstrip().upper().startswith(('SELECT', 'EXPLAIN')):
        raise RuntimeError('Аудит запретил SQL-запись: ' + sql.split()[0])
    return execute(sql, params, many, context)


def original_thumbnailer(source):
    url = source.url if hasattr(source, 'url') else settings.MEDIA_URL + str(source)
    return SimpleNamespace(get_thumbnail=lambda options: SimpleNamespace(url=url))


def audit():
    client = Client(HTTP_HOST='audit.local')
    products = list(Product.objects.filter(is_active=True))
    paths = {reverse('home'), reverse('catalog:housing_catalog'), reverse('catalog:category_index')}
    paths.update(product.get_absolute_url() for product in products)
    paths.update(category.get_absolute_url() for category in public_tree())
    paths.update(brand.get_absolute_url() for brand in Brand.objects.filter(products__is_active=True).distinct())
    paths.update(public_information_paths())
    information_count = InformationMaterial.objects.filter(is_active=True).count()
    issues = []
    checked = 0

    def issue(path, problem, **details):
        issues.append({'path': path, 'problem': problem, **details})

    def fetch(path):
        try:
            return client.get(path, secure=True)
        except Exception as error:
            issue(path, 'request_error', detail=str(error))
            return None

    response = fetch('/sitemap.xml')
    if response is not None:
        if response.status_code != 200:
            issue('/sitemap.xml', 'http_status', status=response.status_code)
        else:
            try:
                urls = [node.text for node in fromstring(response.content).findall('{*}url/{*}loc')]
                actual = {urlsplit(url).path for url in urls}
                if len(urls) != len(set(urls)):
                    issue('/sitemap.xml', 'duplicate_urls')
                for path in sorted(paths - actual):
                    issue(path, 'sitemap_missing')
                for path in sorted(actual - paths):
                    issue(path, 'sitemap_unexpected')
                for url in urls:
                    if not url.startswith('https://audit.local/') or urlsplit(url).query:
                        issue('/sitemap.xml', 'sitemap_noncanonical_url', url=url)
            except Exception as error:
                issue('/sitemap.xml', 'invalid_xml', detail=str(error))
    for path in sorted(paths):
        response = fetch(path)
        checked += 1
        if response is None:
            continue
        if response.status_code != 200:
            issue(path, 'http_status', status=response.status_code)
            continue
        head = BeautifulSoup(response.content, 'html.parser').head
        if head is None:
            issue(path, 'missing_head')
            continue
        canonical = head.find_all('link', rel='canonical')
        expected = 'https://audit.local' + path
        if len(canonical) != 1 or canonical[0].get('href') != expected:
            issue(path, 'canonical_mismatch', expected=expected)
        robots = head.find('meta', attrs={'name': 'robots'})
        if not robots or robots.get('content') != 'index, follow' or 'noindex' in response.get('X-Robots-Tag', ''):
            issue(path, 'public_page_noindex')
        og = head.find('meta', property='og:url')
        if not og or og.get('content') != expected:
            issue(path, 'og_url_mismatch')
        if not head.title or not head.title.get_text(strip=True):
            issue(path, 'missing_title')
        description = head.find('meta', attrs={'name': 'description'})
        if not description or not description.get('content', '').strip():
            issue(path, 'missing_description')
    utility = ['/search/', '/wishlist/', '/catalog/comparison/', '/catalog/recently-viewed/', '/account/login/']
    for path in utility:
        response = fetch(path)
        if response is None:
            continue
        head = BeautifulSoup(response.content, 'html.parser').head
        robots = head.find('meta', attrs={'name': 'robots'}) if head else None
        if response.status_code != 200 or response.get('X-Robots-Tag') != 'noindex, follow' or not robots or robots.get('content') != 'noindex, follow':
            issue(path, 'utility_noindex_mismatch')
    response = fetch('/robots.txt')
    if response is not None and (response.status_code != 200 or b'Sitemap: https://audit.local/sitemap.xml' not in response.content):
        issue('/robots.txt', 'robots_sitemap_missing')
    return {'published_objects': len(products), 'published_information_materials': information_count, 'public_pages_checked': checked,
            'utility_pages_checked': len(utility), 'issues': issues, 'ok': not issues}


class Command(BaseCommand):
    help = 'Проверить публичные страницы жилья, sitemap, canonical и noindex без SQL-записей.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Путь JSON-отчёта внутри patch-backups.')

    def handle(self, *args, **options):
        output = None
        if options['output']:
            root = (Path(settings.BASE_DIR) / 'patch-backups').resolve()
            output = Path(options['output']).resolve()
            if not output.is_relative_to(root):
                raise CommandError('Отчёт необходимо сохранять в patch-backups.')
        with override_settings(ALLOWED_HOSTS=['audit.local'], SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
                               CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}):
            with patch('easy_thumbnails.templatetags.thumbnail.get_thumbnailer', side_effect=original_thumbnailer), connection.execute_wrapper(read_only):
                report = audit()
        text = json.dumps(report, ensure_ascii=False, indent=2)
        self.stdout.write(text)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text + '\n', encoding='utf-8')
        if not report['ok']:
            raise CommandError('Проверка обнаружила проблемы. Подробности в JSON-отчёте.')

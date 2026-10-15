"""Проверка ссылок отображаемого текста без сетевых запросов и SQL-записи."""
from collections import Counter
from urllib.parse import unquote, urljoin, urlsplit
from bs4 import BeautifulSoup
from django.conf import settings
from django.test import Client
from django.urls import resolve, Resolver404, reverse
from .models import InformationMaterial
from .rendering import material_html
from .media import legacy_media_path
from apps.products.prices_html import convert_joomla_source


# Только публичные страницы чтения. Не вызываем обработчики действий и админку.
PUBLIC_VIEWS = {
    ('apps.information.views', 'material_detail'),
    ('apps.information.views', 'material_list'),
    ('apps.products.import_views', 'legacy_item'),
    ('apps.products.views', 'product_detail'),
    ('apps.products.views', 'catalog'),
    ('apps.products.views', 'brand_detail'),
    ('apps.products.category_views', 'category_index'),
    ('apps.products.category_views', 'category_detail'),
    ('apps.products.housing_catalog', 'housing_catalog'),
    ('apps.home.views', 'home'),
    ('apps.home.legal_views', 'public_offer'),
    ('apps.home.legal_views', 'privacy_policy'),
    ('apps.home.legal_views', 'personal_data_consent'),
}
FIELDS = ('intro', 'body', 'extra_body', 'html_insert')
AUDIT_ORIGIN = 'https://audit.local'


def host_key(value):
    host = (value or '').rstrip('.').lower()
    if host.startswith('www.'):
        host = host[4:]
    return host.encode('idna').decode('ascii')


def internal_target(href, base):
    """Вернуть локальный path/query или причину пропуска, не выполняя запрос."""
    href = href.strip()
    if not href or href.startswith('#'):
        return None, 'fragment_or_empty'
    try:
        parsed = urlsplit(urljoin(AUDIT_ORIGIN + base, href))
        if parsed.scheme not in ('http', 'https'):
            return None, 'other_protocol'
        hosts = {host_key('дикарь-сочи.рф'), 'audit.local',
                 host_key(urlsplit(getattr(settings, 'SITE_URL', '')).hostname)}
        if host_key(parsed.hostname) not in hosts:
            return None, 'external'
        # Медиа проверяются отдельным импортом/аудитом, здесь проверяем страницы.
        path = parsed.path or '/'
        decoded = unquote(path)
        prefixes = ('/images/', '/media/', '/static/',
                    urlsplit(settings.MEDIA_URL).path, urlsplit(settings.STATIC_URL).path)
        if any(prefix and decoded.startswith(prefix) for prefix in prefixes):
            return None, 'media_or_static'
        return path + ('?' + parsed.query if parsed.query else ''), None
    except (ValueError, UnicodeError):
        return None, 'invalid_url'


def check_target(client, target):
    seen = set()
    chain = []
    current = target
    for _ in range(6):
        if current in seen:
            return {'problem': 'redirect_loop', 'redirects': chain}
        seen.add(current)
        try:
            match = resolve(unquote(urlsplit(current).path))
        except Resolver404:
            return {'problem': 'missing_route', 'status': 404, 'target': current, 'redirects': chain}
        if (match.func.__module__, match.func.__name__) not in PUBLIC_VIEWS:
            return {'skipped': 'unchecked_route', 'target': current, 'redirects': chain}
        try:
            response = client.get(current, secure=True)
        except Exception as error:
            return {'problem': 'request_error', 'error_type': type(error).__name__, 'target': current, 'redirects': chain}
        status = response.status_code
        if status not in (301, 302, 303, 307, 308):
            result = {'status': status, 'target': current, 'redirects': chain}
            if status != 200:
                result['problem'] = 'http_status'
            return result
        destination, skipped = internal_target(response.get('Location', ''), urlsplit(current).path)
        if skipped:
            return {'skipped': 'redirect_' + skipped, 'target': current, 'redirects': chain}
        chain.append({'from': current, 'to': destination, 'status': status})
        current = destination
    return {'problem': 'too_many_redirects', 'redirects': chain}


def audit_information_links():
    client = Client(HTTP_HOST='audit.local')
    cache = {}
    issues, unchecked, redirected = [], [], []
    skipped = Counter()
    links = 0
    legacy_absolute = 0
    materials = list(InformationMaterial.objects.filter(is_active=True).order_by('pk'))
    for material in materials:
        base = material.get_absolute_url()
        for field in FIELDS:
            value = getattr(material, field)
            soup = BeautifulSoup(material_html(value), 'html.parser')
            source_soup = BeautifulSoup(convert_joomla_source(value), 'html.parser')
            source_hrefs = {node.get('href', '') for node in source_soup.find_all('a', href=True)}
            # Одинаковая ссылка в одном поле требует одной записи в отчёте.
            rendered_hrefs = {node.get('href', '') for node in soup.find_all('a', href=True)}
            # Медиа могут штатно переписываться/скрываться; их проверяет импорт медиа.
            removed_hrefs = {href for href in source_hrefs - rendered_hrefs
                             if href.strip() and not legacy_media_path(href)}
            hrefs = sorted(rendered_hrefs | removed_hrefs)
            for href in hrefs:
                links += 1
                target, reason = internal_target(href, base)
                origin = {'material_id': material.pk, 'joomla_id': material.joomla_id,
                          'title': material.title, 'material_url': base,
                          'admin_url': reverse('admin:information_informationmaterial_change', args=[material.pk]),
                          'field': field, 'href': href}
                if href in removed_hrefs:
                    issues.append({**origin, 'problem': 'link_not_rendered'})
                    continue
                if reason:
                    skipped[reason] += 1
                    if reason == 'invalid_url':
                        issues.append({**origin, 'problem': reason})
                    continue
                if urlsplit(href).netloc:
                    legacy_absolute += 1
                if target not in cache:
                    cache[target] = check_target(client, target)
                result = cache[target]
                entry = {**origin, 'requested_target': target, **result}
                if result.get('problem'):
                    issues.append(entry)
                elif result.get('skipped'):
                    unchecked.append(entry)
                elif result.get('redirects'):
                    redirected.append(entry)
    return {'published_materials': len(materials), 'links_found': links,
            'internal_targets_checked': len(cache), 'absolute_internal_links': legacy_absolute,
            'skipped_counts': dict(sorted(skipped.items())),
            'issue_counts': dict(sorted(Counter(row['problem'] for row in issues).items())), 'issues': issues,
            'unchecked_links': unchecked, 'redirected_links': redirected, 'ok': not issues}

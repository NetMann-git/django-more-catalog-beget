"""Восстановление известных ссылок Joomla только при выводе материала."""
from urllib.parse import urlsplit, urlunsplit
from django.urls import reverse
from .legacy_urls import LEGACY_MATERIAL_PATHS


LEGACY_HOSTS = {'дикарь-сочи.рф'.encode('idna').decode('ascii')}
REVIEW_PATH = next(path for path, joomla_id in LEGACY_MATERIAL_PATHS.items() if joomla_id == 131)


def normalize_content_link(value):
    """Неизвестные адреса оставляем обычному HTML-санитайзеру, без догадок."""
    value = value or ''
    href = value.strip()
    if not href or '\\' in href or any(ord(char) < 32 for char in href):
        return value
    try:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme not in ('', 'http', 'https') or not parsed.hostname:
                return value
            host = parsed.hostname.rstrip('.').lower()
            if host.startswith('www.'):
                host = host[4:]
            if host.encode('idna').decode('ascii') not in LEGACY_HOSTS or parsed.username or parsed.password:
                return value
            ports = (None, 80) if parsed.scheme == 'http' else (None, 443) if parsed.scheme == 'https' else (None, 80, 443)
            if parsed.port not in ports:
                return value
        elif not parsed.path or parsed.path.startswith('//'):
            return value
        path = '/' + parsed.path.lstrip('/') if parsed.path else '/'
        aliases = {'/karta-sochi.html': reverse('information:maps'),
                   '/otzyvy-ob-otdyxe-v-sochi-adlere.html': REVIEW_PATH}
        if path in aliases:
            destination = aliases[path]
        elif path in LEGACY_MATERIAL_PATHS or path == '/':
            destination = path
        else:
            return value
        return urlunsplit(('', '', destination, parsed.query, parsed.fragment))
    except (ValueError, UnicodeError):
        return value

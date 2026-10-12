"""Безопасный вывод текста; исходник материала не изменяется."""
import re
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe
from apps.products.prices_html import sanitize_prices


def material_html(value):
    value = value or ''
    value = re.sub(r'\{tab\s+([^{}]+)\}', lambda match: '<h3>'+str(escape(match[1].split('|')[0]))+'</h3>', value, flags=re.I)
    value = re.sub(r'\{/?tabs?\}', '', value, flags=re.I)
    value = re.sub(r'\{(?:module|loadmodule|loadposition|modal)\b[^{}]*\}', '<p>Этот дополнительный блок пока недоступен.</p>', value, flags=re.I)
    value = re.sub(r'\{/modal\}', '', value, flags=re.I)
    if not re.search(r'<\s*[a-zA-Z!/]', value):
        value = linebreaks(value, autoescape=True)
    soup = BeautifulSoup(sanitize_prices(value), 'html.parser')
    for image in soup.find_all('img'):
        source = image.get('src', '').lstrip('/')
        if source.startswith('images/'):
            root = (Path(settings.MEDIA_ROOT) / 'joomla-information').resolve()
            file = (root / source).resolve()
            if file.is_relative_to(root) and file.is_file():
                image['src'] = settings.MEDIA_URL + 'joomla-information/' + quote(source, safe='/')
            else:
                note = soup.new_tag('span');note['class'] = 'info-page__notice';note.string = 'Изображение пока недоступно.'
                image.replace_with(note)
    return mark_safe(str(soup))

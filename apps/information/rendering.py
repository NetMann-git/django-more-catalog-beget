"""Безопасный вывод текста; исходник материала не изменяется."""
import re
from bs4 import BeautifulSoup
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe
from apps.products.prices_html import sanitize_prices
from .media import media_url, legacy_media_path


def material_html(value):
    value = value or ''
    value = re.sub(r'\{tab\s+([^{}]+)\}', lambda match: '<h3>'+str(escape(match[1].split('|')[0]))+'</h3>', value, flags=re.I)
    value = re.sub(r'\{/?tabs?\}', '', value, flags=re.I)
    value = re.sub(r'\{(?:module|loadmodule|loadposition|modal)\b[^{}]*\}', '<p>Этот дополнительный блок пока недоступен.</p>', value, flags=re.I)
    value = re.sub(r'\{/modal\}', '', value, flags=re.I)
    if not re.search(r'<\s*[a-zA-Z!/]', value):
        value = linebreaks(value, autoescape=True)
    soup = BeautifulSoup(sanitize_prices(value), 'html.parser')
    for node in soup.find_all(['img', 'video', 'source', 'a']):
        attr = 'href' if node.name == 'a' else 'src'
        value = node.get(attr, '')
        if legacy_media_path(value):
            url = media_url(value)
            if url:
                node[attr] = url
            elif node.name == 'a':
                node.unwrap()
            else:
                note = soup.new_tag('span');note['class'] = 'info-page__notice';note.string = 'Изображение пока недоступно.'
                node.replace_with(note)
    return mark_safe(str(soup))

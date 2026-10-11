"""Чистый текст метаданных без изменения исходных полей."""
import re
from bs4 import BeautifulSoup
from django.utils.text import Truncator


def plain_metadata(value):
    """Удалить разметку и содержимое script/style, сохранив текст и сущности."""
    soup = BeautifulSoup(str(value or ''), 'html.parser')
    for element in soup(['script', 'style']):
        element.decompose()
    return re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).strip()


def description_metadata(meta, *fallbacks):
    """Явное SEO-описание целиком; резервный текст ограничить 160 символами."""
    explicit = plain_metadata(meta)
    if explicit:
        return explicit
    for value in fallbacks:
        text = plain_metadata(value)
        if text:
            return Truncator(text).chars(160)
    return ''

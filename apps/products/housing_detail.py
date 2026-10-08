"""Явный публичный набор разделов жилья; внутренние поля не читаются."""
import re
from bs4 import BeautifulSoup
from django.utils.html import linebreaks
from django.utils.safestring import mark_safe
from .prices_html import sanitize_prices

SECTIONS = (
    ('description', 'Об объекте', (('description', 'Об объекте'),)),
    ('location', 'Месторасположение', (('location_description', 'Месторасположение'),)),
    ('rooms', 'Номера и размещение', (('rooms_description', 'Номера и размещение'),)),
    ('meals', 'Питание', (('meals_description', 'Питание'),)),
    ('beach', 'Море и пляж', (('beach_description', 'Пляж'), ('beach_distance_description', 'Расстояние до пляжа'))),
    ('conditions', 'Условия и услуги', (('special_conditions', 'Особые условия'), ('additional_services', 'Дополнительные услуги'))),
    ('booking', 'Бронирование', (('booking_conditions', 'Условия бронирования'), ('checkin_checkout_description', 'Расчётный час'))),
    ('prices', 'Цены и размещение', (('price_description', 'Цены'), ('included_services', 'Входит в стоимость'), ('paid_services', 'За дополнительную плату'), ('extra_beds_description', 'Дополнительные места'))),
)


def public_html(value: str) -> str:
    """Показать безопасный HTML либо текст с сохранением абзацев."""
    value = (value or '').strip()
    if not value:
        return ''
    html = sanitize_prices(value if re.search(r'<\s*[a-zA-Z!/]', value) or '{source' in value else linebreaks(value, autoescape=True))
    parsed = BeautifulSoup(html, 'html.parser')
    if not parsed.get_text(strip=True) and not parsed.find(['img', 'video', 'iframe', 'table']):
        return ''
    return mark_safe(html)


def phones(value: str) -> list[dict]:
    """Сделать ссылку только для однозначного номера; пояснения сохраняются."""
    result = []
    for text in re.split(r'[,;\n]+', value or ''):
        text = text.strip()
        if not text:
            continue
        digits = re.sub(r'[^0-9]', '', text)
        valid = re.fullmatch(r'\+?[0-9 ()-]+', text) and 7 <= len(digits) <= 15
        result.append({'text': text, 'href': ('tel:' + ('+' if text.startswith('+') else '') + digits) if valid else ''})
    return result


def housing_context(product) -> dict:
    """Собрать только публичные поля, без SQL на каждое значение удобства."""
    from .map_data import product_map
    sections = []
    for slug, title, fields in SECTIONS:
        blocks = [{'label': label, 'html': public_html(getattr(product, name))} for name, label in fields]
        blocks = [block for block in blocks if block['html']]
        if blocks:
            sections.append({'slug': slug, 'title': title, 'blocks': blocks})
    groups = {}
    for row in product.attributes.select_related('attribute_type', 'attribute_value'):
        if not row.attribute_value_id:
            continue
        kind, value = row.attribute_type, row.attribute_value
        group = groups.setdefault(kind.pk, {'name': kind.name, 'icon': kind.icon, 'values': []})
        group['values'].append({'text': value.value, 'icon': value.icon or kind.icon})
    contacts = []
    for name, phone in ((product.contact_name, product.contact_phone), (product.additional_contact_name, product.additional_contact_phone)):
        if name.strip() or phone.strip():
            contacts.append({'name': name, 'phones': phones(phone)})
    gallery = list(product.gallery.all())
    return {
        'housing_sections': sections,
        'housing_map': product_map(product),
        'housing_short_description': public_html(product.short_description),
        'housing_attributes': list(groups.values()),
        'housing_contacts': contacts,
        'housing_has_contacts': bool(contacts or product.contact_email),
        'housing_gallery': gallery,
        'housing_cover': product.image or (gallery[0].image if gallery else None),
        'housing_gallery_count': len(gallery) + bool(product.image),
    }

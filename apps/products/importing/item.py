"""Пробный импорт одного полного снимка JBZoo без перезаписи чужих объектов."""
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.products.cache import CatalogCache
from apps.products.map_data import apply_map_import
from apps.products.models import Brand, Category, Product


class ItemImportError(ValueError):
    """Исходные данные или база не позволяют безопасно выполнить импорт."""


FIELDS = {
    'Коротко': 'short_description', 'Район:': 'district_text',
    'Подзаголовок': 'subtitle', 'Телефон:': 'contact_phone',
    'Контакт:': 'contact_name', 'Доп. телефон:': 'additional_contact_phone',
    'Доп. контакт:': 'additional_contact_name', 'E-mail:': 'contact_email',
    'Адрес:': 'address', 'Месторасположение': 'location_description',
    'Номерной фонд или описание комнат частного сектора и квартир': 'rooms_description',
    'Питание': 'meals_description', 'Пляж': 'beach_description',
    'Расстояние до пляжа': 'beach_distance_description',
    'Особые условия': 'special_conditions', 'Дополнительные услуги': 'additional_services',
    'Условия бронирования': 'booking_conditions', 'Расчетный час': 'checkin_checkout_description',
    'Входит в стоимость': 'included_services', 'За дополнительную плату': 'paid_services',
    'Дополнительные места': 'extra_beds_description', 'Цены': 'price_description',
    'Скрытое инфомационное поле': 'internal_notes',
}


def read_snapshot(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('item'), dict):
        raise ItemImportError('Ожидается снимок одного объекта, schema=1.')
    if not isinstance(data.get('id'), int) or data['id'] <= 0:
        raise ItemImportError('Некорректный ID Joomla.')
    if not re.fullmatch(r'[-a-zA-Z0-9_]{1,255}', data.get('alias', '')):
        raise ItemImportError('Некорректный алиас.')
    parsed = urlsplit(data.get('url', ''))
    if parsed.scheme != 'https' or parsed.hostname != 'xn----7sblqcj4aok5d9b.xn--p1ai':
        raise ItemImportError('Некорректный исходный URL.')
    if parsed.path.replace('//', '/') != '/' + data.get('legacy_prefix', 'properties-list') + '/' + data['alias'] + '.html':
        raise ItemImportError('URL не соответствует алиасу.')
    return data


def media_plan(data, media_source):
    """Проверить все файлы до записи базы; коллизии файлов запрещены."""
    source_root = Path(media_source).resolve()
    target_root = Path(settings.MEDIA_ROOT).resolve()
    result = []
    seen = set()
    for entry in data['media']:
        rel = entry['path']
        if not re.fullmatch(r'images/uploads/user_[0-9]+/[\w .()-]+\.(jpg|jpeg|png|webp|gif|mp4)', rel, flags=re.I) or rel in seen:
            raise ItemImportError('Недопустимый или повторный путь медиа.')
        seen.add(rel)
        source = (source_root / rel).resolve()
        destination = (target_root / 'jbzoo' / str(data['id']) / rel).resolve()
        if not source.is_relative_to(source_root) or not destination.is_relative_to(target_root):
            raise ItemImportError('Путь медиа выходит за пределы папки.')
        for file in (source, destination):
            if file == source or file.exists():
                if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != entry['sha256']:
                    raise ItemImportError(f'Файл отсутствует или отличается от снимка: {file}')
        result.append((rel, source, destination))
    return result


def scalar(element):
    rows = element.get('data', {})
    if set(rows) != {'0'} or not isinstance(rows['0'].get('value'), str):
        raise ItemImportError(f'Неподдерживаемое значение: {element.get("name")}')
    return rows['0']['value']


def prepare(data, media_source):
    raw = data['item']
    if raw.get('state') not in ('0', '1') or raw.get('access') != '1':
        raise ItemImportError('Неподдерживаемый статус или уровень доступа.')
    # _root is Joomla's virtual root, not an importable category.
    categories = [slug for slug in raw['categories'].values() if slug != '_root']
    primary = raw['config']['primary_category']
    categories = list(dict.fromkeys(categories + [primary]))
    found = {c.slug: c for c in Category.objects.filter(slug__in=categories)}
    if set(found) != set(categories):
        raise ItemImportError('Сначала импортируйте категории: ' + ', '.join(set(categories) - set(found)))
    existing = Product.objects.filter(joomla_id=data['id']).first()
    collision = Product.objects.filter(slug=data['alias']).exclude(joomla_id=data['id']).exists()
    if collision:
        raise ItemImportError('Алиас занят существующим объектом. Перезапись запрещена.')
    archived_names = [e['name'].strip() or e['type'] for e in raw['elements'].values() if e['name'].strip() not in set(FIELDS) | {'Карта яндекс', 'Тип жилья', 'Главное Фото'}]
    if existing:
        if existing.joomla_source != data or existing.slug != data['alias']:
            raise ItemImportError('Снимок или алиас изменились. Автоматическая перезапись запрещена.')
        return existing, found, [], archived_names, True
    plan = media_plan(data, media_source)
    obj = Product(title=raw['name'], slug=data['alias'], joomla_id=data['id'],
                  joomla_url=data['url'], joomla_source=data, is_active=raw['state'] == '1',
                  category=found[primary], article=str(data['id']), currency='RUB',
                  meta_title=raw['metadata']['title'], meta_description=raw['metadata']['description'])
    archived = []
    main = None
    brand_name = None
    mapped = set()
    for element in raw['elements'].values():
        name = element['name'].strip()
        if name in FIELDS:
            if name in mapped:
                raise ItemImportError('Повтор раздела: ' + name)
            mapped.add(name)
            setattr(obj, FIELDS[name], scalar(element))
        elif name == 'Карта яндекс':
            apply_map_import(obj, element['data'])
        elif name == 'Тип жилья':
            brand_name = element['data']['0']['list-0']
        elif name == 'Главное Фото':
            main = element['data']['0']['file']
        else:
            archived.append(name or element['type'])
    obj.price_description_source = obj.price_description
    for rel, _, _ in plan:
        url = settings.MEDIA_URL.rstrip('/') + '/jbzoo/' + str(data['id']) + '/' + rel
        # Rewrite only matching media src attributes; original HTML remains archived.
        for field in set(FIELDS.values()):
            value = getattr(obj, field)
            value = re.sub(r'(\bsrc\s*=\s*["\'])/?' + re.escape(rel) + r'(["\'])', lambda m: m[1] + url + m[2], value)
            setattr(obj, field, value)
    if main:
        if main not in {rel for rel, _, _ in plan}:
            raise ItemImportError('Главное фото отсутствует в списке медиа.')
        obj.image = 'jbzoo/' + str(data['id']) + '/' + main
    if brand_name:
        obj.brand = Brand.objects.filter(name=brand_name).first()
        if obj.brand is None:
            brand_slug = {'Гостевые дома':'gostevye-doma', 'Квартиры':'kvartiry', 'Частный сектор':'chastnyj-sektor'}.get(brand_name)
            if not brand_slug or Brand.objects.filter(slug=brand_slug).exists():
                raise ItemImportError('Тип жилья не сопоставлен: ' + brand_name)
            obj.brand = Brand(name=brand_name, slug=brand_slug)
            obj.brand.full_clean()
    try:
        obj.full_clean()
    except ValidationError as exc:
        raise ItemImportError(str(exc)) from exc
    return obj, found, plan, archived, False


def import_item(data, media_source, apply=False):
    """Атомарная запись БД; новые файлы удаляются при ошибке записи."""
    created_files = []
    try:
        with transaction.atomic():
            obj, categories, plan, archived, unchanged = prepare(data, media_source)
            if apply and not unchanged:
                for _, source, destination in plan:
                    if not destination.exists():
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with destination.open('xb') as output, source.open('rb') as input_file:
                            created_files.append(destination)
                            shutil.copyfileobj(input_file, output)
                if obj.brand is not None and obj.brand.pk is None:
                    brand = obj.brand
                    brand.save()
                    obj.brand = brand
                obj.save()
                obj.categories.set(categories.values())
                transaction.on_commit(CatalogCache.clear_catalog)
            return {'id':data['id'], 'title':obj.title, 'slug':obj.slug, 'published':obj.is_active,
                    'result':'unchanged' if unchanged else 'created' if apply else 'check',
                    'categories':list(categories), 'primary':obj.category.slug,
                    'media':len(data['media']), 'gallery_complete':data['gallery_complete'],
                    'archived_elements':archived, 'product_pk':obj.pk,
                    'preview_url':f'/catalog/manage/{obj.pk}/preview/' if obj.pk else None}
    except Exception:
        for file in created_files:
            file.unlink(missing_ok=True)
        raise

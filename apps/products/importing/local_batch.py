"""Три проверенных объекта с фотографиями из локальных папок пользователя."""
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from PIL import Image
from django.conf import settings
from django.db import transaction

from apps.products.cache import CatalogCache
from apps.products.models import ProductGalleryImage
from .gallery import filename_order
from .item import FIELDS, ItemImportError, prepare

APPROVED = {1096:'user_396', 1963:'user_548', 1036:'user_378'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def read_local_batch(fixture, media_source, approved=None):
    approved = APPROVED if approved is None else approved
    source = Path(media_source).resolve()
    data = json.loads(Path(fixture).read_text(encoding='utf-8'))
    if not isinstance(data, list) or len(data) != len(approved) or {x['id'] for x in data} != set(approved):
        raise ItemImportError('Список объектов не соответствует выбранной группе.')
    result = []
    for original in data:
        item = copy.deepcopy(original)
        folder_name = approved[item['id']]
        elements = item['item']['elements'].values()
        galleries = [e.get('data', {}).get('value') for e in elements if e['name'] == 'Галерея']
        if folder_name not in galleries:
            raise ItemImportError('Папка не соответствует исходному объекту.')
        path = urlsplit(item['url']).path.replace('//', '/')
        if path != '/' + item['legacy_prefix'] + '/' + item['alias'] + '.html':
            raise ItemImportError('Исходный URL не соответствует алиасу.')
        folder = source / 'images/uploads' / folder_name
        if not folder.is_dir() or not folder.resolve().is_relative_to(source):
            raise ItemImportError(f'Добавьте папку: {folder}')
        files = sorted([f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS], key=lambda f:filename_order(f.name))
        if not files:
            raise ItemImportError(f'В папке нет фотографий: {folder}')
        cover = next(e['data']['0']['file'] for e in elements if e['name'] == 'Главное Фото')
        if cover not in ['images/uploads/' + folder_name + '/' + f.name for f in files]:
            raise ItemImportError('Нет главного фото: ' + cover)
        item['media'] = []
        for file in files:
            if not file.resolve().is_relative_to(folder.resolve()) or not re.fullmatch(r'[\w .()-]+\.(jpg|jpeg|png|webp|gif)', file.name, flags=re.I):
                raise ItemImportError('Недопустимый путь/имя фотографии: ' + str(file))
            try:
                with Image.open(file) as image:
                    image.verify()
            except (OSError, ValueError) as exc:
                raise ItemImportError('Повреждённая фотография: ' + str(file)) from exc
            if len('jbzoo/'+str(item['id'])+'/images/uploads/'+folder_name+'/'+file.name) > 100:
                raise ItemImportError('Слишком длинное имя файла: ' + file.name)
            item['media'].append({'path':'images/uploads/' + folder_name + '/' + file.name,
                                  'size':file.stat().st_size, 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
        # Include media referenced in HTML, rather than silently leaving old relative URLs.
        known = {e['path'] for e in item['media']}
        for element in elements:
            if element['name'].strip() not in FIELDS:
                continue
            for value in element.get('data', {}).values():
                if not isinstance(value, dict):
                    continue
                for tag in BeautifulSoup(value.get('value', ''), 'html.parser').find_all(src=True):
                    src = tag['src']
                    if src.startswith(('images/', '/images/')):
                        rel = src.lstrip('/')
                        if rel in known:
                            continue
                        if not rel.startswith('images/uploads/' + folder_name + '/') or not re.fullmatch(r'images/uploads/user_[0-9]+/[\w .()-]+\.(jpg|jpeg|png|webp|gif|mp4)', rel, flags=re.I):
                            raise ItemImportError('Дополнительное медиа требует явного переноса: ' + src)
                        file = (source / rel).resolve()
                        if not file.is_relative_to(folder.resolve()) or not file.is_file():
                            raise ItemImportError('Отсутствует медиа из HTML: ' + rel)
                        item['media'].append({'path':rel,'size':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
                        known.add(rel)
        item['local_gallery'] = [e['path'] for e in item['media'] if Path(e['path']).suffix.lower() in IMAGE_EXTENSIONS and e['path'] != cover]
        item['gallery_complete'] = True
        ignored = [f.name for f in folder.iterdir() if f.is_dir() or f.suffix.lower() not in IMAGE_EXTENSIONS and 'images/uploads/'+folder_name+'/'+f.name not in known]
        result.append((item, ignored))
    return result


def import_local_batch(batch, media_source, apply=False):
    """Проверить всю группу до записи; откатить всю группу при ошибке."""
    created_files = []
    report = []
    try:
        with transaction.atomic():
            # Prepare every object before copying even the first file.
            prepared = [(data, ignored, prepare(data, media_source)) for data, ignored in batch]
            for data, ignored, (obj, categories, plan, archived, unchanged) in prepared:
                if unchanged:
                    report.append({'id':data['id'], 'result':'unchanged', 'title':obj.title,
                        'preview_url':f'/catalog/manage/{obj.pk}/preview/', 'gallery_photos':len(data['local_gallery']), 'ignored':ignored})
                    continue
                if apply:
                    hashes = {entry['path']:entry['sha256'] for entry in data['media']}
                    for rel, source, destination in plan:
                        if not destination.exists():
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            with destination.open('xb') as output, source.open('rb') as input_file:
                                created_files.append(destination)
                                shutil.copyfileobj(input_file, output)
                            if hashlib.sha256(destination.read_bytes()).hexdigest() != hashes[rel]:
                                raise ItemImportError('Исходный файл изменился во время импорта: ' + rel)
                    if obj.brand is not None and obj.brand.pk is None:
                        # A prepared brand can already have been saved by another item.
                        from apps.products.models import Brand
                        brand = Brand.objects.filter(name=obj.brand.name).first() or obj.brand
                        if brand.pk is None:
                            brand.save()
                        obj.brand = brand
                    obj.save()
                    obj.categories.set(categories.values())
                    for order, rel in enumerate(data['local_gallery']):
                        ProductGalleryImage.objects.create(product=obj, image='jbzoo/'+str(data['id'])+'/'+rel,
                            alt=obj.title, sort_order=order)
                report.append({'id':data['id'], 'result':'created' if apply else 'check', 'title':obj.title,
                    'published':obj.is_active, 'categories':list(categories), 'primary':obj.category.slug,
                    'gallery_photos':len(data['local_gallery']), 'photos_with_cover':len(data['local_gallery'])+1,
                    'order':[Path(p).name for p in data['local_gallery']], 'ignored':ignored,
                    'archived_elements':archived, 'preview_url':f'/catalog/manage/{obj.pk}/preview/' if obj.pk else None})
            if apply:
                transaction.on_commit(CatalogCache.clear_catalog, robust=True)
        return report
    except Exception:
        for file in created_files:
            file.unlink(missing_ok=True)
        raise

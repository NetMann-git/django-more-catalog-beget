"""Проверенный импорт галереи: порядок имён, контроль файлов и повторный запуск."""
import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image
from django.conf import settings
from django.db import transaction

from apps.products.cache import CatalogCache
from apps.products.models import Product, ProductGalleryImage
from .item import ItemImportError


def filename_order(name):
    """Сортировать числовые части по числу: photo2 раньше photo10."""
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                 for part in re.split(r'(\d+)', name)) + ((0, name),)


def read_manifest(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or data.get('joomla_id') != 2425 or data.get('folder') != 'user_606':
        raise ItemImportError('Шаг 23.1 принимает только проверенную галерею объекта 2425.')
    names = [entry['name'] for entry in data['images']]
    if len(set(names)) != len(names) or data['cover'] not in names:
        raise ItemImportError('Повтор имени или отсутствие главного фото в списке.')
    if any(not re.fullmatch(r'[a-zA-Z0-9_-]+\.(jpg|jpeg|png)', name) for name in names):
        raise ItemImportError('Недопустимое имя фотографии.')
    if names != sorted(names, key=filename_order):
        raise ItemImportError('Список не соответствует порядку имён файлов.')
    return data


def read_images(source, manifest):
    """Не распаковывать пути из ZIP; читать только известные проверенные файлы."""
    source = Path(source)
    expected = {entry['name']: entry for entry in manifest['images']}
    blobs = {}
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            files = [entry for entry in archive.infolist() if not entry.is_dir()]
            required = {manifest['folder'] + '/' + name for name in expected}
            if len(files) != len(required) or {entry.filename for entry in files} != required:
                raise ItemImportError('Состав ZIP отличается от проверенного списка галереи.')
            for entry in files:
                name = entry.filename.split('/')[1]
                if entry.file_size != expected[name]['size']:
                    raise ItemImportError('Размер фотографии отличается: ' + name)
                blobs[name] = archive.read(entry)
    elif source.is_dir():
        root = source.resolve()
        files = [p for p in root.iterdir() if p.is_file()]
        if {p.name for p in files} != set(expected):
            raise ItemImportError('Состав папки отличается от проверенного списка галереи.')
        for file in files:
            if not file.resolve().is_relative_to(root):
                raise ItemImportError('Файл выходит за пределы папки.')
            if file.stat().st_size != expected[file.name]['size']:
                raise ItemImportError('Размер фотографии отличается: ' + file.name)
            blobs[file.name] = file.read_bytes()
    else:
        raise ItemImportError('Укажите ZIP галереи или папку user_606.')
    for name, blob in blobs.items():
        if hashlib.sha256(blob).hexdigest() != expected[name]['sha256']:
            raise ItemImportError('Контрольная сумма фотографии отличается: ' + name)
        try:
            with Image.open(io.BytesIO(blob)) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise ItemImportError('Файл не является исправной фотографией: ' + name) from exc
    return blobs


def gallery_plan(manifest, blobs, lock=False):
    queryset = Product.objects.select_for_update() if lock else Product.objects.all()
    product = queryset.filter(joomla_id=manifest['joomla_id']).first()
    if not product or product.slug != manifest['alias']:
        raise ItemImportError('Сначала импортируйте объект 2425 шагом 23. Алиас должен совпадать.')
    elements = product.joomla_source.get('item', {}).get('elements', {}).values()
    if not any(e.get('name') == 'Галерея' and e.get('data', {}).get('value') == manifest['folder'] for e in elements):
        raise ItemImportError('Папка галереи не соответствует исходному объекту JBZoo.')
    root = Path(settings.MEDIA_ROOT).resolve()
    planned, names = [], set()
    for order, entry in enumerate(e for e in manifest['images'] if e['name'] != manifest['cover']):
        name = 'jbzoo/' + str(product.joomla_id) + '/images/uploads/' + manifest['folder'] + '/' + entry['name']
        destination = (root / name).resolve()
        if not destination.is_relative_to(root):
            raise ItemImportError('Путь назначения выходит за пределы media.')
        if destination.exists() and (not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != entry['sha256']):
            raise ItemImportError('Коллизия файла в media: ' + name)
        matches = list(product.gallery.filter(image=name))
        if len(matches) > 1:
            raise ItemImportError('В базе уже есть повторные записи: ' + name)
        names.add(name)
        planned.append({'name':name, 'file':destination, 'blob':blobs[entry['name']],
                        'existing':matches[0] if matches else None, 'order':order})
    # Keep manually added photos and their order. Imported photos follow them.
    manual_orders = list(product.gallery.exclude(image__in=names).values_list('sort_order', flat=True))
    offset = max(manual_orders, default=-1) + 1
    hashes = defaultdict(list)
    for entry in manifest['images']:
        hashes[entry['sha256']].append(entry['name'])
    return product, planned, offset, [v for v in hashes.values() if len(v) > 1]


def import_gallery(manifest, blobs, apply=False):
    """Сохранить записи атомарно; не менять архив объекта и существующие правки."""
    created_files = []
    try:
        with transaction.atomic():
            product, planned, offset, duplicates = gallery_plan(manifest, blobs, lock=apply)
            new_rows = sum(row['existing'] is None for row in planned)
            new_files = sum(not row['file'].exists() for row in planned)
            if apply:
                for row in planned:
                    destination = row['file']
                    if not destination.exists():
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with destination.open('xb') as output:
                            created_files.append(destination)
                            output.write(row['blob'])
                    if row['existing'] is None:
                        ProductGalleryImage.objects.create(product=product, image=row['name'],
                            alt=product.title, sort_order=offset + row['order'])
                if new_rows:
                    transaction.on_commit(CatalogCache.clear_catalog, robust=True)
            return {'joomla_id':product.joomla_id, 'product_pk':product.pk,
                    'mode':'apply' if apply else 'check', 'source_photos':len(manifest['images']),
                    'cover_excluded':manifest['cover'], 'gallery_photos':len(planned),
                    'new_records':new_rows, 'existing_records':len(planned)-new_rows,
                    'new_files':new_files, 'order':[Path(row['name']).name for row in planned],
                    'identical_content':duplicates, 'preview_url':f'/catalog/manage/{product.pk}/preview/'}
    except Exception:
        for file in created_files:
            file.unlink(missing_ok=True)
        raise

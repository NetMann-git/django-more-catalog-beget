"""Исходные медиа материалов: проверка путей и копирование без обработки."""
import hashlib
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import CommandError
from apps.products.prices_html import convert_joomla_source


EXCLUDED_MEDIA = frozenset(['images/14-dnei/050.png', 'images/14-dnei/090.png', 'images/14-dnei/10.gif', 'images/14-dnei/140.png', 'images/14-dnei/18.gif', 'images/14-dnei/180.png', 'images/14-dnei/230.png', 'images/14-dnei/270.png', 'images/14-dnei/28.gif', 'images/14-dnei/320.png', 'images/14-dnei/360.png', 'images/14-dnei/7.gif', 'images/14-dnei/ind10.gif', 'images/14-dnei/ind7.gif', 'images/14-dnei/ind8.gif', 'images/14-dnei/ind9.gif', 'images/14-dnei/n1.gif', 'images/14-dnei/n10.gif', 'images/14-dnei/n18.gif', 'images/14-dnei/n28.gif', 'images/14-dnei/n7.gif', 'images/14-dnei/phase0.jpg', 'images/14-dnei/phase1.jpg', 'images/14-dnei/phase15.jpg', 'images/14-dnei/phase16.jpg', 'images/14-dnei/phase2.jpg', 'images/14-dnei/phase3.jpg', 'images/14-dnei/phase4.jpg', 'images/14-dnei/phase5.jpg', 'images/14-dnei/phase6.jpg', 'images/camera/mor-vokzal.jpg', 'images/camera/olimp-park-sch.jpg', 'images/camera/roza-xytor-derev.jpg', 'images/camera/sputnik.jpg'])


EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm'}


def legacy_media_path(value):
    value = str(value or '').split('|||')[0].strip()
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or '\\' in value:
        return None
    path = unquote(parsed.path).lstrip('/')
    parts = path.split('/')
    if not path.startswith('images/') or any(part in ('', '.', '..') for part in parts) or Path(path).suffix.lower() not in EXTENSIONS:
        return None
    return path


def local_path(root, relative):
    root = Path(root).resolve()
    file = (root / relative).resolve()
    if not file.is_relative_to(root):
        raise CommandError('Медиа-путь выходит за разрешённую папку: ' + relative)
    return file


def media_url(value):
    relative = legacy_media_path(value)
    if not relative:
        return None
    root = Path(settings.MEDIA_ROOT) / 'joomla-information'
    if local_path(root, relative).is_file():
        return settings.MEDIA_URL + 'joomla-information/' + quote(relative, safe='/')
    return None


def material_paths(material):
    paths = set()
    cover = legacy_media_path(material.image_source)
    if cover:paths.add(cover)
    for value in (material.intro, material.body, material.extra_body, material.html_insert):
        soup = BeautifulSoup(convert_joomla_source(value), 'html.parser')
        for node in soup.find_all(['img', 'video', 'source', 'a']):
            relative = legacy_media_path(node.get('href' if node.name == 'a' else 'src', ''))
            if relative:paths.add(relative)
    return paths - EXCLUDED_MEDIA


def file_hash(file):
    digest = hashlib.sha256()
    with Path(file).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):digest.update(chunk)
    return digest.hexdigest()


def media_plan(materials, source):
    source = Path(source).resolve()
    if not source.is_dir():raise CommandError('Исходная папка не найдена: ' + str(source))
    target = Path(settings.MEDIA_ROOT) / 'joomla-information'
    paths = sorted(set().union(*(material_paths(material) for material in materials)))
    entries, missing, conflicts = [], [], []
    for relative in paths:
        original, destination = local_path(source, relative), local_path(target, relative)
        if not original.is_file():
            missing.append(relative);continue
        digest = file_hash(original)
        same = destination.is_file() and file_hash(destination) == digest
        if destination.exists() and not same:
            conflicts.append(relative)
        entries.append({'path': relative, 'sha256': digest, 'already_identical': same})
    return {'expected_files': len(paths), 'available_files': len(entries),
            'already_identical': sum(row['already_identical'] for row in entries),
            'missing_files': missing, 'conflicts': conflicts, 'entries': entries}

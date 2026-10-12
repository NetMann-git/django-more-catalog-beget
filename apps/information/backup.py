"""Согласованная резервная копия SQLite только в patch-backups."""
import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import CommandError


def backup_database():
    database = settings.DATABASES['default']
    source = Path(str(database['NAME'])).resolve()
    if database['ENGINE'] != 'django.db.backends.sqlite3' or not source.is_file():
        raise CommandError('Требуется файловая SQLite-база для резервной копии.')
    folder = Path(settings.BASE_DIR) / 'patch-backups'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('information-step57-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target

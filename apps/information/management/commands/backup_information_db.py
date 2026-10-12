from django.core.management.base import BaseCommand
from apps.information.backup import backup_database


class Command(BaseCommand):
    help = 'Сохранить копию SQLite в patch-backups перед миграцией материалов.'

    def handle(self, *args, **options):
        self.stdout.write(str(backup_database()))

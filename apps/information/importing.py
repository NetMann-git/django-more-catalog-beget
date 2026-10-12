"""Проверяемый импорт с сохранением исходных ячеек обоих экспортов."""
import hashlib
import json
from pathlib import Path
from django.core.management.base import CommandError
from django.db import transaction
from .models import InformationCategory, InformationMaterial


FIXTURE = Path(__file__).parent / 'fixtures/information_import.json'


def load_plan():
    plan = json.loads(FIXTURE.read_text(encoding='utf-8'))
    if plan.get('version') != 1 or len(plan.get('categories', [])) != 14 or len(plan.get('materials', [])) != 193:
        raise CommandError('Структура или количество записей плана отличается от проверенного экспорта.')
    for archive in plan['archives']:
        data = (FIXTURE.parent / archive['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != archive['sha256']:
            raise CommandError('Хеш исходного архива отличается: ' + archive['file'])
    return plan


def check_plan(plan):
    for rows, model in [(plan['categories'], InformationCategory), (plan['materials'], InformationMaterial)]:
        if len({row['joomla_id'] for row in rows}) != len(rows) or len({row['slug'] for row in rows}) != len(rows):
            raise CommandError('Повторяющийся ID или псевдоним в плане.')
        for row in rows:
            existing = model.objects.filter(joomla_id=row['joomla_id']).first()
            if existing and existing.source != row['source']:
                raise CommandError(f'Исходники ID {row["joomla_id"]} отличаются. Автоматическая перезапись запрещена.')
            if model.objects.filter(slug=row['slug']).exclude(joomla_id=row['joomla_id']).exists():
                raise CommandError('Псевдоним уже занят: ' + row['slug'])
    slugs = {row['slug'] for row in plan['categories']}
    for row in plan['materials']:
        refs = row['category_slugs'] + ([row['primary_slug']] if row['primary_slug'] else [])
        if any(slug not in slugs for slug in refs):
            raise CommandError('Неизвестная категория материала.')


@transaction.atomic
def import_plan(plan):
    check_plan(plan)
    categories = {}
    created_ids = set()
    new_categories = new_materials = 0
    for row in plan['categories']:
        values = {key: value for key, value in row.items() if key != 'parent_id'}
        category, created = InformationCategory.objects.get_or_create(joomla_id=row['joomla_id'], defaults=values)
        categories[row['slug']] = category
        if created:
            created_ids.add(category.pk)
        new_categories += created
    by_id = {row.joomla_id: row for row in categories.values()}
    for row in plan['categories']:
        parent = by_id.get(row['parent_id'])
        category = categories[row['slug']]
        if category.pk in created_ids and category.parent_id != (parent.pk if parent else None):
            category.parent = parent
            category.save(update_fields=['parent'])
    for row in plan['materials']:
        values = {key: value for key, value in row.items() if key not in ('category_slugs', 'primary_slug')}
        values['primary_category'] = categories.get(row['primary_slug'])
        material, created = InformationMaterial.objects.get_or_create(joomla_id=row['joomla_id'], defaults=values)
        if created:
            material.categories.set([categories[slug] for slug in row['category_slugs']])
        new_materials += created
    return {'new_categories': new_categories, 'new_materials': new_materials,
            'categories': InformationCategory.objects.count(), 'materials': InformationMaterial.objects.count(),
            'published': InformationMaterial.objects.filter(is_active=True).count()}

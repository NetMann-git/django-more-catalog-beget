"""Проверка и атомарный импорт исходного CSV JBZoo."""
import csv
import io
import re
import zipfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.products.cache import CatalogCache
from apps.products.models import Category


class CategoryImportError(ValueError):
    """Экспорт или состояние базы не допускают безопасный импорт."""


def read_categories(path):
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".csv")]
            if len(names) != 1:
                raise CategoryImportError("В ZIP должен быть ровно один CSV категорий.")
            data = archive.read(names[0])
    else:
        data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    required = {"id", "name", "alias", "parent", "ordering", "published", "description"}
    if not required.issubset(reader.fieldnames or []):
        raise CategoryImportError("CSV не содержит обязательных колонок JBZoo.")
    rows = list(reader)
    if not rows:
        raise CategoryImportError("Экспорт пуст.")
    ids, aliases = set(), set()
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise CategoryImportError("Повреждённая строка CSV.")
        try:
            identifier = int(row["id"])
            int(row["ordering"])
        except ValueError as exc:
            raise CategoryImportError("ID и порядок должны быть целыми числами.") from exc
        alias = row["alias"]
        if identifier <= 0 or identifier in ids or alias in aliases:
            raise CategoryImportError("Повтор ID/алиаса или неположительный ID.")
        if not re.fullmatch(r"[-a-zA-Z0-9_]{1,255}", alias):
            raise CategoryImportError(f"Недопустимый алиас: {alias!r}")
        if not row["name"].strip() or len(row["name"]) > 255:
            raise CategoryImportError("Пустое или слишком длинное название.")
        if row["published"] not in {"0", "1"}:
            raise CategoryImportError("published должен быть 0 или 1.")
        ids.add(identifier)
        aliases.add(alias)
    parents = {r["alias"]: r["parent"] for r in rows}
    for alias in aliases:
        visited = set()
        current = alias
        while current:
            if current in visited:
                raise CategoryImportError(f"Цикл родителей: {alias}")
            if current not in parents:
                raise CategoryImportError(f"Отсутствует родитель: {current}")
            visited.add(current)
            current = parents[current]
    return rows


@transaction.atomic
def import_categories(rows, apply=False):
    """Сопоставлять только по ID Joomla/алиасу; не удалять существующие записи."""
    existing = list(Category.objects.select_for_update().all())
    by_id = {c.joomla_id: c for c in existing if c.joomla_id is not None}
    by_slug = {c.slug: c for c in existing}
    targets, used = {}, set()
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    for row in rows:
        identifier = int(row["id"])
        obj = by_id.get(identifier)
        slug_obj = by_slug.get(row["alias"])
        if obj is not None and obj.slug != row["alias"]:
            raise CategoryImportError(f"ID {identifier}: алиас в базе изменён; автоматическая перезапись запрещена.")
        if slug_obj is not None and slug_obj.joomla_id not in (None, identifier):
            raise CategoryImportError(f"Алиас занят другим ID Joomla: {row['alias']}")
        obj = obj or slug_obj or Category()
        if obj.pk is not None and obj.pk in used:
            raise CategoryImportError("Две строки сопоставлены одной категории.")
        if obj.pk is not None:
            used.add(obj.pk)
        targets[row["alias"]] = obj
    # Строки упорядочены по глубине, поэтому родители сохраняются первыми.
    by_alias = {r["alias"]: r for r in rows}
    def depth(row):
        result, parent = 0, row["parent"]
        while parent:
            result += 1
            parent = by_alias[parent]["parent"]
        return result
    for row in sorted(rows, key=depth):
        obj = targets[row["alias"]]
        parent = targets.get(row["parent"])
        values = {
            "title": row["name"], "slug": row["alias"],
            "joomla_id": int(row["id"]), "sort_order": int(row["ordering"]),
            "is_published": row["published"] == "1",
            "description": row["description"],
            "meta_title": row.get("metadata_title", ""),
            "meta_description": row.get("metadata_description", ""),
            "meta_keywords": row.get("metadata_keywords", ""),
            "joomla_source": row,
        }
        new = obj.pk is None
        changed = any(getattr(obj, k) != v for k, v in values.items())
        changed = changed or (parent is not None and parent.pk is None) or obj.parent_id != (parent.pk if parent else None)
        counts["created" if new else "updated" if changed else "unchanged"] += 1
        for key, value in values.items():
            setattr(obj, key, value)
        if apply:
            obj.parent = parent
            try:
                obj.full_clean()
            except ValidationError as exc:
                raise CategoryImportError(str(exc)) from exc
            if new or changed:
                obj.save()
    if apply:
        transaction.on_commit(CatalogCache.clear_catalog)
    return counts

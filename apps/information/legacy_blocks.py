"""Инвентаризация неподдерживаемых вставок Joomla; код не исполняется."""
import re
from collections import Counter
from django.urls import reverse
from .models import InformationMaterial


UNSUPPORTED_BLOCK_RE = re.compile(r'\{(?P<kind>module|loadmodule|loadposition|modal)\b(?P<argument>[^{}]*)\}', re.I)
FIELDS = ('intro', 'body', 'extra_body', 'html_insert')


def legacy_blocks(value):
    for match in UNSUPPORTED_BLOCK_RE.finditer(value or ''):
        kind = match['kind'].lower()
        argument = match['argument'].strip()
        numeric = re.fullmatch(r'([0-9]{1,12})(?:[\s,|].*)?', argument, re.S) if kind == 'module' else None
        module_id = int(numeric[1]) if numeric and int(numeric[1]) > 0 else None
        yield {'kind': kind, 'argument': argument, 'module_id': module_id, 'token': match[0]}


def audit_information_blocks(include_unpublished=False):
    queryset = InformationMaterial.objects.all()
    if not include_unpublished:
        queryset = queryset.filter(is_active=True)
    materials = list(queryset.only('pk', 'joomla_id', 'title', 'slug', 'is_active', *FIELDS).order_by('pk'))
    entries, grouped = [], {}
    kinds = Counter()
    occurrences = 0
    for material in materials:
        blocks = []
        for field in FIELDS:
            counts = Counter((block['kind'], block['argument'], block['module_id'], block['token'])
                             for block in legacy_blocks(getattr(material, field)))
            for (kind, argument, module_id, token), count in sorted(counts.items(), key=lambda item: item[0][3]):
                blocks.append({'field': field, 'kind': kind, 'argument': argument,
                               'module_id': module_id, 'token': token, 'occurrences': count})
                key = (kind, str(module_id) if module_id is not None else argument)
                if key not in grouped:
                    grouped[key] = {'kind': kind, 'module_id': module_id, 'arguments': set(),
                                    'occurrences': 0, 'material_ids': set(), 'published_material_ids': set()}
                group = grouped[key]
                group['arguments'].add(argument)
                group['occurrences'] += count
                group['material_ids'].add(material.pk)
                if material.is_active:
                    group['published_material_ids'].add(material.pk)
                occurrences += count
                kinds[kind] += count
        if blocks:
            entries.append({'id': material.pk, 'joomla_id': material.joomla_id, 'title': material.title,
                            'is_active': material.is_active, 'url': material.get_absolute_url(),
                            'admin_url': reverse('admin:information_informationmaterial_change', args=[material.pk]),
                            'blocks': blocks})
    groups = []
    for key in sorted(grouped):
        group = grouped[key]
        for name in ('arguments', 'material_ids', 'published_material_ids'):
            group[name] = sorted(group[name])
        group['materials_count'] = len(group['material_ids'])
        group['published_materials_count'] = len(group['published_material_ids'])
        groups.append(group)
    return {'include_unpublished': include_unpublished, 'materials_checked': len(materials),
            'published_materials_checked': sum(material.is_active for material in materials),
            'affected_materials': len(entries), 'affected_published_materials': sum(row['is_active'] for row in entries),
            'occurrences': occurrences, 'unresolved_blocks': len(groups),
            'numeric_module_ids': sorted({row['module_id'] for row in groups if row['module_id'] is not None}),
            'by_kind': dict(sorted(kinds.items())), 'blocks': groups, 'materials': entries, 'ok': not groups}

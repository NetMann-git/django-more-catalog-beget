"""Проверяемые предложения дополнительных категорий. Запись в БД отсутствует."""
import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlencode
from django.core.exceptions import ValidationError
from apps.products.category_views import public_tree
from apps.products.category_coverage import category_coverage
from apps.products.map_data import coordinate_pair
from apps.products.models import Product

# Это текстовые признаки, не географические границы и не правила применения.
REGIONS = {
    73: ('Адлер', r'\b(?:адлер\w*|сириус\w*)\b'),
    77: ('Кудепста', r'\bкудепст\w*\b'),
    114: ('Хоста', r'\bхост(?:а|е|у|ы)\b'),
    79: ('Сочи', r'(?<!большое )\bсочи\b'),
    80: ('Дагомыс', r'\bдагомыс\w*\b'),
    81: ('Лоо', r'\bлоо\b'),
    85: ('Вардане', r'\bвардане\b'),
    82: ('Лазаревское', r'\bлазаревск\w*\b'),
    83: ('Красная Поляна', r'\b(?:красн\w* полян\w*|эсто[ -]садок\w*)\b'),
    86: ('Туапсе', r'\b(?:туапс\w*|ольгинк\w*|агой\w*|небуг\w*|новомихайловск\w*|джубг\w*|лермонтово|шепси|дедеркой)\b'),
    84: ('Абхазия', r'\b(?:абхаз\w*|гагр\w*|пицунд\w*|сухум\w*|нов\w* афон\w*|цандрипш\w*|багрипш\w*|гудаут\w*)\b'),
}
SOCHI_REGIONS = {73, 77, 114, 80, 81, 85, 82, 83}


def normalize(value):
    return ' '.join(str(value or '').casefold().replace('ё', 'е').split())


def snapshot_hash(product, assigned=None):
    if assigned is None:
        assigned = sorted(set(product.categories.values_list('pk', flat=True)) |
                          ({product.category_id} if product.category_id else set()))
    snapshot = {'pk': product.pk, 'joomla_id': product.joomla_id, 'is_active': product.is_active,
        'slug': product.slug, 'primary_category_id': product.category_id,
        'category_ids': sorted(assigned), 'title': product.title, 'address': product.address,
        'district_text': product.district_text, 'map_coordinates': product.map_coordinates,
        'source': product.joomla_source}
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def proposal(product, categories):
    source = product.joomla_source if isinstance(product.joomla_source, dict) else {}
    item = source.get('item', {})
    item = item if isinstance(item, dict) else {}
    tags = item.get('tags', {})
    tags = list(tags.values()) if isinstance(tags, dict) else tags if isinstance(tags, list) else []
    texts = [('title', product.title), ('address', product.address), ('district_text', product.district_text)]
    texts += [('source_tag', tag) for tag in tags if isinstance(tag, str)]
    evidence = []
    candidates = set()
    for field, value in texts:
        for region, (label, pattern) in REGIONS.items():
            if re.search(pattern, normalize(value)):
                evidence.append({'field': field, 'value': value, 'region_joomla_id': region, 'region': label})
                candidates.add(region)
    notes = []
    # «г. Сочи, Адлер» — общий город и конкретный район, не два курорта.
    if 79 in candidates and candidates & SOCHI_REGIONS:
        candidates.remove(79)
        notes.append('general_sochi_mention_ignored')
    coordinate_status, marker = 'missing', None
    try:
        marker = coordinate_pair(product.map_coordinates)
        if marker is not None:
            coordinate_status = 'valid'
    except ValidationError:
        coordinate_status = 'invalid'
    status = 'proposed' if len(candidates) == 1 else 'review'
    reason = 'single_text_region' if len(candidates) == 1 else 'conflicting_regions' if candidates else 'no_specific_region'
    target = next(iter(candidates)) if len(candidates) == 1 else None
    category = categories.get(target)
    if target is not None and category is None:
        status, reason = 'review', 'target_category_not_public_or_missing'
    assigned = sorted(set(product.categories.values_list('pk', flat=True)) | ({product.category_id} if product.category_id else set()))
    fingerprint = snapshot_hash(product, assigned)
    return {'id': product.pk, 'joomla_id': product.joomla_id, 'title': product.title,
        'url': product.get_absolute_url(), 'admin_url': f'/admin/products/product/{product.pk}/change/',
        'primary_category_id': product.category_id, 'existing_category_ids': assigned,
        'status': status, 'reason': reason, 'candidate_region_joomla_ids': sorted(candidates),
        'suggested_category_id': category.pk if category else None,
        'suggested_category_title': category.title if category else None,
        'evidence': evidence, 'notes': notes, 'coordinate_status': coordinate_status,
        'marker_coordinates': product.map_coordinates,
        'coordinate_check_url': 'https://yandex.ru/maps/?' + urlencode({'pt': ','.join(marker), 'z': 15}) if marker else None,
        'snapshot_sha256': fingerprint}


def region_proposals():
    coverage = category_coverage()
    outside_ids = [row['id'] for row in coverage['outside_objects']]
    categories = {row.joomla_id: row for row in public_tree() if row.joomla_id in REGIONS}
    rows = [proposal(product, categories) for product in Product.objects.filter(pk__in=outside_ids)
            .prefetch_related('categories').order_by('pk')]
    counts = Counter(row['suggested_category_title'] for row in rows if row['status'] == 'proposed')
    return {'schema': 2, 'applied': False, 'published_objects': coverage['published_objects'],
        'objects_outside_maps': len(rows), 'proposed_objects': sum(row['status'] == 'proposed' for row in rows),
        'manual_review_objects': sum(row['status'] == 'review' for row in rows),
        'proposed_by_category': dict(sorted(counts.items())),
        'review_reasons': dict(Counter(row['reason'] for row in rows if row['status'] == 'review')),
        'coordinate_status_counts': dict(Counter(row['coordinate_status'] for row in rows)), 'items': rows}

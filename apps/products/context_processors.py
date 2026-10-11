"""Публичные счётчики сравнения и истории без устаревших ID."""
from .public_lists import active_product_ids


def comparison_ids(request):
    return {'comparison_ids': active_product_ids(request.session.get('comparison', []))}


def recently_viewed_ids(request):
    return {'recently_viewed_ids': active_product_ids(request.session.get('recently_viewed', []))}

"""Публичные категории жилья с множественными привязками объектов."""
from collections import defaultdict
from types import SimpleNamespace

from django.core.paginator import Paginator, InvalidPage
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from .housing_detail import public_html
from .models import Category, Product


PAGE_SIZE = 12


def public_tree():
    categories = list(Category.objects.filter(is_published=True).exclude(slug='_root'))
    by_id = {category.pk: category for category in categories}
    def visible(category):
        visited = set()
        while category.parent_id:
            if category.pk in visited or category.parent_id not in by_id:
                return False
            visited.add(category.pk)
            category = by_id[category.parent_id]
        return True
    return [category for category in categories if visible(category)]


def category_index(request):
    from .region_proposals import REGIONS

    illustrations = {
        73: 'promenade', 77: 'coastal-village', 114: 'forest-coast',
        79: 'promenade', 80: 'coastal-town', 81: 'coastal-village',
        85: 'forest-coast', 82: 'pebble-beach', 83: 'mountain-valley',
        86: 'coastal-town', 84: 'pebble-beach',
    }
    categories = public_tree()
    children = defaultdict(list)
    for category in categories:
        children[category.parent_id].append(category)
    return render(request, 'products/housing_categories.html', {
        'housing_public_page': True, 'housing_section': 'categories',
        'groups': [
            {
                'root': root,
                'title': REGIONS[root.joomla_id][0] if root.joomla_id in REGIONS else root.title,
                'image': f'products/images/resorts/{illustrations[root.joomla_id]}.webp'
                if root.joomla_id in illustrations else '',
                'children': children[root.pk],
            }
            for root in children[None]
        ],
        'page': SimpleNamespace(seo_title='Категории жилья', search_description='Жильё для отдыха по курортам и типам размещения.'),
    })


@ensure_csrf_cookie
def category_detail(request, slug):
    from apps.information.map_navigation import category_map_links
    from .housing_related import housing_cards
    categories = public_tree()
    category = next((category for category in categories if category.slug == slug), None)
    if category is None:
        raise Http404
    canonical = category.get_absolute_url()
    if request.path != canonical:
        query = request.GET.urlencode()
        return redirect(canonical + ('?' + query if query else ''), permanent=True)
    selected = {category.pk}
    while True:
        descendants = {child.pk for child in categories if child.parent_id in selected}
        expanded = selected | descendants
        if expanded == selected:
            break
        selected = expanded
    products = Product.objects.filter(is_active=True).filter(
        Q(category_id__in=selected) | Q(categories__pk__in=selected)
    ).distinct().select_related('brand', 'location').prefetch_related('gallery').order_by('title', 'pk')
    paginator = Paginator(products, PAGE_SIZE)
    try:
        page_obj = paginator.page(request.GET.get('page', '1'))
    except InvalidPage as exc:
        raise Http404 from exc
    favorites = (
        request.user.favorites.values_list('product_id', flat=True)
        if request.user.is_authenticated else request.session.get('wishlist', [])
    )
    by_id = {entry.pk: entry for entry in categories}
    ancestors = []
    parent = category.parent_id
    while parent:
        ancestor = by_id[parent]
        ancestors.append(ancestor)
        parent = ancestor.parent_id
    return render(request, 'products/housing_category.html', {
        'housing_public_page': True, 'housing_section': 'categories',
        'category_map_links': category_map_links(category, categories),
        'category': category, 'description_html': public_html(category.description),
        'ancestors': list(reversed(ancestors)),
        'children': [entry for entry in categories if entry.parent_id == category.pk],
        'cards': housing_cards(page_obj), 'page_obj': page_obj, 'wishlist_ids': set(favorites),
        'canonical_path': canonical + (f'?page={page_obj.number}' if page_obj.number > 1 else ''),
        'page': SimpleNamespace(seo_title=category.meta_title or category.title, search_description=category.meta_description),
    })

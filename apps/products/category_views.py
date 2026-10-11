"""Публичные категории жилья с множественными привязками объектов."""
from types import SimpleNamespace

from django.core.paginator import Paginator, InvalidPage
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render

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
    categories = public_tree()
    return render(request, 'products/housing_categories.html', {
        'roots': [category for category in categories if category.parent_id is None],
        'categories': categories,
        'page': SimpleNamespace(seo_title='Категории жилья', search_description='Жильё для отдыха по курортам и типам размещения.'),
    })


def category_detail(request, slug):
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
    ).distinct().select_related('brand').prefetch_related('gallery').order_by('title', 'pk')
    paginator = Paginator(products, PAGE_SIZE)
    try:
        page_obj = paginator.page(request.GET.get('page', '1'))
    except InvalidPage as exc:
        raise Http404 from exc
    cards = []
    for product in page_obj:
        gallery = list(product.gallery.all())
        cards.append({'product': product, 'cover': product.image or (gallery[0].image if gallery else None)})
    by_id = {entry.pk: entry for entry in categories}
    ancestors = []
    parent = category.parent_id
    while parent:
        ancestor = by_id[parent]
        ancestors.append(ancestor)
        parent = ancestor.parent_id
    return render(request, 'products/housing_category.html', {
        'category': category, 'description_html': public_html(category.description),
        'ancestors': list(reversed(ancestors)),
        'children': [entry for entry in categories if entry.parent_id == category.pk],
        'cards': cards, 'page_obj': page_obj,
        'canonical_path': canonical + (f'?page={page_obj.number}' if page_obj.number > 1 else ''),
        'page': SimpleNamespace(seo_title=category.meta_title or category.title, search_description=category.meta_description),
    })

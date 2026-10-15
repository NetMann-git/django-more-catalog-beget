"""Публичные материалы, категории и сохранённые адреса Joomla."""
from types import SimpleNamespace
from urllib.parse import urlencode
from django.core.paginator import Paginator, InvalidPage
from django.db.models import Q
from django.http import Http404, HttpResponsePermanentRedirect
from django.views.decorators.http import require_safe
from .content_links import content_aliases, REVIEWS_ALIAS
from django.shortcuts import get_object_or_404, redirect, render
from .models import InformationCategory, InformationMaterial
from .forms import InformationSearchForm
from .rendering import material_html
from .maps import material_map, select_map_point
from .map_navigation import map_category_links
from .related import related_materials
from .navigation import category_path, material_navigation


def public_categories():
    rows = list(InformationCategory.objects.filter(is_published=True))
    by_id = {row.pk: row for row in rows}
    def visible(row):
        visited = set()
        while row.parent_id:
            if row.pk in visited or row.parent_id not in by_id:
                return False
            visited.add(row.pk);row = by_id[row.parent_id]
        return True
    return [row for row in rows if visible(row)]


def material_list(request, slug=None, maps=False):
    categories = public_categories()
    products = InformationMaterial.objects.filter(is_active=True)
    title = 'Информационные материалы'
    category = None
    if maps:
        products = products.filter(kind='map');title = 'Материалы с картами'
    if slug:
        category = next((row for row in categories if row.slug == slug), None)
        if category is None:
            raise Http404
        ids = {category.pk}
        while True:
            expanded = ids | {row.pk for row in categories if row.parent_id in ids}
            if expanded == ids:break
            ids = expanded
        products = products.filter(Q(categories__pk__in=ids) | Q(primary_category_id__in=ids)).distinct()
        title = category.title
    form = InformationSearchForm(request.GET)
    valid_search = form.is_valid()
    query = form.cleaned_data.get('q', '') if valid_search else ''
    search_active = bool(request.GET.get('q', '').strip())
    if search_active:
        request.seo_noindex = True
    if not valid_search:
        products = products.none()
    elif query:
        from apps.search.services import SearchService
        products = products.filter(pk__in=SearchService.information_search(query).values_list('pk', flat=True))
    query_string = urlencode({'q': query}) if query else ''
    try:
        page_obj = Paginator(products.order_by('title', 'pk'), 12).page(request.GET.get('page', 1))
    except InvalidPage as error:
        raise Http404 from error
    return render(request, 'information/list.html', {
        'housing_public_page': True, 'information_public_page': True, 'categories': categories, 'category': category,
        'page_obj': page_obj, 'title': title, 'search_form': form, 'search_query': query,
        'search_active': search_active, 'search_query_string': query_string,
        'pagination_prefix': '?' + query_string + ('&' if query_string else ''),
        'category_ancestors': category_path(category.pk, categories)[:-1] if category else [],
        'subcategories': [row for row in categories if category and row.parent_id == category.pk],
        'maps_only': maps,
        'category_description': material_html(category.description) if category else '',
        'page': SimpleNamespace(seo_title=category.meta_title or title if category else title,
                              search_description=category.meta_description if category else 'Полезная информация об отдыхе в Сочи и на побережье.'),
    })


def material_detail(request, slug=None, joomla_id=None):
    lookup = {'joomla_id': joomla_id} if joomla_id is not None else {'slug': slug}
    material = get_object_or_404(InformationMaterial, is_active=True, **lookup)
    if request.path != material.get_absolute_url():
        return redirect(material.get_absolute_url(), permanent=True)
    return render(request, 'information/detail.html', material_detail_context(material, request.GET.get('object', '')))


def material_detail_context(material, selected_id=''):
    public_rows = public_categories()
    visible = {row.pk for row in public_rows}
    category_rows = list(material.categories.all())
    navigation = material_navigation(material, public_rows, category_rows)
    blocks = [material_html(value) for value in (material.intro, material.body, material.extra_body, material.html_insert) if value.strip()]
    return {'housing_public_page': True, 'information_public_page': True,
        'material': material, 'page': material,
        'related_materials': related_materials(material, visible, {row.pk for row in category_rows}),
        'map_category_links': map_category_links(material), **navigation, 'blocks': blocks, 'map_data': select_map_point(material_map(material), selected_id)}


@require_safe
def legacy_content_redirect(request):
    destination = content_aliases().get(request.path_info)
    if destination is None:
        raise Http404
    if request.path_info == REVIEWS_ALIAS:
        # Не делаем публичным переход на скрытый или отсутствующий материал.
        material = get_object_or_404(InformationMaterial.objects.only('joomla_id', 'slug'),
                                     joomla_id=131, is_active=True)
        destination = material.get_absolute_url()
    query = request.META.get('QUERY_STRING', '')
    if query:
        destination += '?' + query
    return HttpResponsePermanentRedirect(destination)

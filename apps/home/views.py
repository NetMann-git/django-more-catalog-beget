"""Главная страница каталога отдыха «Дикарь-Сочи»."""
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.information.maps import material_root_categories
from apps.information.models import InformationMaterial
from apps.products.category_views import public_tree
from apps.products.housing_catalog import HousingFilterForm
from apps.products.models import Brand, Product
from apps.products.region_proposals import REGIONS


FEATURED_RESORTS = (73, 82, 81, 114)


def _map_destination(categories, resorts, resort_slug, brand):
    resort = next((row for row in resorts if row.slug == resort_slug), None)
    maps = InformationMaterial.objects.filter(is_active=True, kind='map').prefetch_related('map_categories')
    if resort_slug and resort is None:
        return reverse('information:maps')
    if resort:
        material = next(
            (row for row in maps.order_by('pk') if row.joomla_id != 841 and material_root_categories(row, categories) == [resort]),
            None,
        )
    else:
        material = next((row for row in maps if row.joomla_id == 841), None)
    if material is None:
        return reverse('information:maps')
    query = '?' + urlencode({'type': brand.pk}) if brand else ''
    return material.get_absolute_url() + query + '#housing-resort-map'


@ensure_csrf_cookie
def home(request: HttpRequest) -> HttpResponse:
    """Подбор и последние опубликованные объекты с исходными адресами."""
    categories = public_tree()
    resorts = [row for row in categories if row.joomla_id in REGIONS]
    resorts.sort(key=lambda row: REGIONS[row.joomla_id][0])
    products = Product.objects.filter(is_active=True)
    brands = list(Brand.objects.filter(products__is_active=True).distinct().order_by('sort_order', 'name', 'pk'))
    if request.GET.get('view') == 'map':
        brand = next((row for row in brands if row.slug == request.GET.get('housing_type')), None)
        return redirect(_map_destination(categories, resorts, request.GET.get('category'), brand))

    form = HousingFilterForm(categories=categories, brands=brands)
    form.fields['category'].label = 'Курорт'
    form.fields['category'].choices = [('', 'Все курорты')] + [
        (row.slug, REGIONS[row.joomla_id][0]) for row in resorts
    ]
    form.fields['housing_type'].choices = [('', 'Все типы жилья')] + [
        (row.slug, row.name) for row in brands
    ]
    cards = []
    for product in products.select_related('brand', 'location').prefetch_related('gallery').order_by('-pk')[:6]:
        gallery = list(product.gallery.all())
        cards.append({'product': product, 'cover': product.image or (gallery[0].image if gallery else None)})
    favorites = (
        request.user.favorites.values_list('product_id', flat=True)
        if request.user.is_authenticated else request.session.get('wishlist', [])
    )
    resorts_by_id = {row.joomla_id: row for row in resorts}
    return render(request, 'home/home.html', {
        'housing_public_page': True,
        'housing_filter_form': form,
        'housing_home_cards': cards,
        'housing_home_types': brands,
        'housing_destinations': [
            {'slug': resorts_by_id[key].slug, 'title': REGIONS[key][0]}
            for key in FEATURED_RESORTS if key in resorts_by_id
        ],
        'wishlist_ids': set(favorites),
    })

"""Главная страница каталога отдыха «Дикарь-Сочи»."""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.products.category_views import public_tree
from apps.products.housing_catalog import HousingFilterForm
from apps.products.models import Brand, Product


REGION_IDS = {73, 77, 114, 79, 80, 81, 85, 82, 86, 84, 83}


def home(request: HttpRequest) -> HttpResponse:
    """Подбор и последние опубликованные объекты с исходными адресами."""
    categories = public_tree()
    products = Product.objects.filter(is_active=True)
    brands = list(Brand.objects.filter(products__is_active=True).distinct().order_by('sort_order', 'name', 'pk'))
    cards = []
    for product in products.select_related('brand').prefetch_related('gallery').order_by('-pk')[:6]:
        gallery = list(product.gallery.all())
        cards.append({'product': product, 'cover': product.image or (gallery[0].image if gallery else None)})
    return render(request, 'home/home.html', {
        'housing_filter_form': HousingFilterForm(categories=categories, brands=brands),
        'housing_count': products.count(), 'housing_home_cards': cards,
        'housing_home_types': brands,
        'housing_destinations': [category for category in categories if category.joomla_id in REGION_IDS],
    })

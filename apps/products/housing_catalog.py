"""Подбор жилья по опубликованным категориям и исходному типу."""
from types import SimpleNamespace

from django import forms
from django.core.paginator import InvalidPage, Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render

from .category_views import PAGE_SIZE, public_tree
from .models import Brand, Product


class HousingFilterForm(forms.Form):
    q = forms.CharField(label='Название или адрес', required=False, max_length=120)
    category = forms.ChoiceField(label='Курорт / категория', required=False)
    housing_type = forms.ChoiceField(label='Тип жилья', required=False)

    def __init__(self, *args, categories, brands, **kwargs):
        super().__init__(*args, **kwargs)
        by_id = {category.pk: category for category in categories}
        choices = [('', 'Все категории')]
        for category in categories:
            names = [category.title]
            parent = category.parent_id
            while parent in by_id:
                names.append(by_id[parent].title)
                parent = by_id[parent].parent_id
            choices.append((category.slug, ' / '.join(reversed(names))))
        self.fields['category'].choices = choices
        self.fields['housing_type'].choices = [('', 'Все типы'), ('untyped', 'Тип не указан')] + [(brand.slug, brand.name) for brand in brands]


def housing_catalog(request):
    categories = public_tree()
    products = Product.objects.filter(is_active=True)
    brands = list(Brand.objects.filter(products__is_active=True).distinct().order_by('name', 'pk'))
    form = HousingFilterForm(request.GET, categories=categories, brands=brands)
    if not form.is_valid():
        products = products.none()
    else:
        values = form.cleaned_data
        selected = next((category for category in categories if category.slug == values['category']), None)
        if selected:
            ids = {selected.pk}
            while True:
                expanded = ids | {category.pk for category in categories if category.parent_id in ids}
                if expanded == ids:
                    break
                ids = expanded
            products = products.filter(Q(category_id__in=ids) | Q(categories__pk__in=ids)).distinct()
        if values['housing_type'] == 'untyped':
            products = products.filter(brand__isnull=True)
        elif values['housing_type']:
            products = products.filter(brand__slug=values['housing_type'])
        if values['q']:
            # SQLite LIKE does not fold Cyrillic; use Unicode consistently across databases.
            query = values['q'].casefold()
            matched_ids = [pk for pk, title, address, district in
                           products.values_list('pk', 'title', 'address', 'district_text').iterator(chunk_size=1000)
                           if any(query in (value or '').casefold() for value in (title, address, district))]
            products = products.filter(pk__in=matched_ids)
    products = products.select_related('brand').prefetch_related('gallery').order_by('title', 'pk')
    paginator = Paginator(products, PAGE_SIZE)
    try:
        page_obj = paginator.page(request.GET.get('page', '1'))
    except InvalidPage as exc:
        raise Http404 from exc
    cards = []
    for product in page_obj:
        gallery = list(product.gallery.all())
        cards.append({'product': product, 'cover': product.image or (gallery[0].image if gallery else None)})
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'products/housing_catalog.html', {
        'housing_public_page': True, 'housing_section': 'housing',
        'filter_form': form, 'cards': cards, 'page_obj': page_obj,
        'pagination_query': params.urlencode(),
        'page': SimpleNamespace(seo_title='Подбор жилья для отдыха', search_description='Подбор гостевых домов, квартир и гостиниц по курорту, категории и типу жилья.'),
    })

"""Подбор жилья по опубликованным категориям и исходному типу."""
from types import SimpleNamespace

from django import forms
from django.core.paginator import InvalidPage, Paginator
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.information.maps import housing_map_data

from .category_views import PAGE_SIZE, public_tree
from .housing_related import housing_cards
from .models import AttributeValue, Brand, Product, ProductAttribute


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


class CatalogFilterForm(HousingFilterForm):
    price_min = forms.DecimalField(label='Цена от, ₽', required=False, min_value=0, max_digits=10, decimal_places=2)
    price_max = forms.DecimalField(label='Цена до, ₽', required=False, min_value=0, max_digits=10, decimal_places=2)
    amenities = forms.ModelMultipleChoiceField(
        label='Удобства', required=False, queryset=AttributeValue.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(['category', 'housing_type', 'q', 'price_min', 'price_max', 'amenities'])
        self.fields['amenities'].queryset = AttributeValue.objects.filter(
            attribute_type__slug='amenities', product_attributes__product__is_active=True,
        ).distinct()

    def clean(self):
        values = super().clean()
        low, high = values.get('price_min'), values.get('price_max')
        if low is not None and high is not None and low > high:
            self.add_error('price_max', 'Максимальная цена должна быть не ниже минимальной.')
        return values


@ensure_csrf_cookie
def housing_catalog(request):
    categories = public_tree()
    products = Product.objects.filter(is_active=True)
    brands = list(Brand.objects.filter(products__is_active=True).distinct().order_by('name', 'pk'))
    form = CatalogFilterForm(request.GET, categories=categories, brands=brands)
    map_view = request.GET.get('view') == 'map'
    selected = None
    chips = []
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
        for name, lookup in [('price_min', 'price__gte'), ('price_max', 'price__lte')]:
            if values[name] is not None:
                products = products.filter(currency='RUB', **{lookup: values[name]})
        for amenity in values['amenities']:
            products = products.filter(
                attributes__attribute_type_id=amenity.attribute_type_id,
                attributes__attribute_value_id=amenity.pk,
            ).distinct()
        if values['q']:
            # SQLite LIKE does not fold Cyrillic; use Unicode consistently across databases.
            query = values['q'].casefold()
            matched_ids = [pk for pk, title, address, district in
                           products.values_list('pk', 'title', 'address', 'district_text').iterator(chunk_size=1000)
                           if any(query in (value or '').casefold() for value in (title, address, district))]
            products = products.filter(pk__in=matched_ids)
        for field in form:
            value = values[field.name]
            if field.name == 'amenities':
                labels = [(str(item.pk), item.value) for item in value]
            elif value is None or value == '':
                labels = []
            elif field.name in ('category', 'housing_type'):
                labels = [(str(value), dict(field.field.choices)[value])]
            elif field.name == 'q':
                labels = [(str(value), value)]
            else:
                labels = [(str(value), f'{field.label.removesuffix(", ₽")} {value} ₽')]
            for key, label in labels:
                remaining = request.GET.copy()
                remaining.pop('page', None)
                remaining.setlist(field.name, [
                    item for item in remaining.getlist(field.name) if item != key
                ] if field.name == 'amenities' else [])
                chips.append({'label': label, 'query': remaining.urlencode()})
    products = products.order_by('title', 'pk')
    page_obj = None
    cards = []
    map_data = None
    if map_view:
        map_data = housing_map_data(products, include_photos=True)
        total = products.count()
    else:
        products = products.select_related('brand', 'location').prefetch_related(
            'gallery', Prefetch('attributes', queryset=ProductAttribute.objects.filter(
                attribute_type__slug='amenities', attribute_value__isnull=False,
            ).select_related('attribute_value'), to_attr='catalog_amenities'),
        )
        paginator = Paginator(products, PAGE_SIZE)
        try:
            page_obj = paginator.page(request.GET.get('page', '1'))
        except InvalidPage as exc:
            raise Http404 from exc
        cards = housing_cards(page_obj)
        total = paginator.count
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('view', None)
    list_query = params.urlencode()
    params['view'] = 'map'
    favorites = (
        request.user.favorites.values_list('product_id', flat=True)
        if request.user.is_authenticated else request.session.get('wishlist', [])
    )
    return render(request, 'products/housing_catalog.html', {
        'housing_public_page': True, 'housing_section': 'housing',
        'filter_form': form, 'cards': cards, 'page_obj': page_obj,
        'pagination_query': list_query, 'map_query': params.urlencode(),
        'map_view': map_view, 'map_data': map_data, 'filter_chips': chips,
        'result_count': total, 'selected_category': selected, 'wishlist_ids': set(favorites),
        'page': SimpleNamespace(seo_title='Подбор жилья для отдыха', search_description='Подбор гостевых домов, квартир и гостиниц по курорту, категории и типу жилья.'),
    })

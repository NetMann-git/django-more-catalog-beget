# apps/search/services.py

from apps.products.models import Product, ProductAttribute
from .models import SearchQuery


class SearchService:
    LIMIT = 8

    @staticmethod
    def search(query):
        """
        Поиск товаров по запросу (для страницы результатов).
        """
        query = (query or '').strip().casefold()
        if not query:
            return Product.objects.none()
        # SQLite не выполняет регистронезависимый поиск кириллицы через LIKE.
        fields = ('title', 'article', 'short_description', 'description',
                  'address', 'district_text')
        matched_ids = [row[0] for row in
                       Product.objects.filter(is_active=True)
                       .values_list('pk', *fields).iterator()
                       if any(query in (value or '').casefold() for value in row[1:])]
        return Product.objects.filter(pk__in=matched_ids, is_active=True).order_by('title', 'pk')

    @staticmethod
    def information_search(query):
        from apps.information.models import InformationMaterial
        query = (query or '').strip().casefold()
        if not query:
            return InformationMaterial.objects.none()
        fields = ('title', 'subtitle', 'intro', 'body', 'extra_body')
        ids = [row[0] for row in InformationMaterial.objects.filter(is_active=True)
               .values_list('pk', *fields).iterator()
               if any(query in (value or '').casefold() for value in row[1:])]
        return InformationMaterial.objects.filter(pk__in=ids, is_active=True).defer(
            'source', 'body', 'extra_body', 'html_insert').order_by('title', 'pk')

    @staticmethod
    def combined_search(query):
        results = [{'kind': 'housing', 'object': product} for product in
                   SearchService.search(query).select_related('brand').prefetch_related('gallery')]
        results += [{'kind': 'information', 'object': material} for material in
                    SearchService.information_search(query)]
        return sorted(results, key=lambda row: (row['object'].title.casefold(), row['kind'], row['object'].pk))

    @staticmethod
    def suggest(query, request=None):
        from apps.products.category_views import public_tree
        query = (query or '').strip()[:120]
        if len(query) < 2:
            return []
        q = query.casefold()
        categories = sorted(public_tree(), key=lambda item: (item.title, item.pk))
        visible_ids = {category.pk for category in categories}

        def cover(product):
            gallery = list(product.gallery.all())
            image = product.image or (gallery[0].image if gallery else None)
            return image.url if image else None

        products = SearchService.search(query).select_related('category', 'brand').prefetch_related('gallery')[:SearchService.LIMIT]
        results = [{
            'type': 'product', 'id': product.pk, 'title': product.title,
            'url': product.get_absolute_url(), 'image': cover(product),
            'address': product.address,
            'brand': product.brand.name if product.brand else None,
            'category': product.category.title if product.category_id in visible_ids else None,
            'price': str(product.price) if product.price is not None else None,
            'currency': product.currency, 'badges': [],
        } for product in products]
        material_results = [{'type': 'information', 'id': material.pk, 'title': material.title,
                             'kind': material.kind, 'url': material.get_absolute_url(),
                             'image': material.cover_url}
                            for material in SearchService.information_search(query)[:4]]
        from itertools import zip_longest
        results = [item for pair in zip_longest(results, material_results) for item in pair if item is not None]
        category_results = [{'type': 'category', 'title': category.title,
                     'url': category.get_absolute_url()}
                    for category in categories if q in category.title.casefold()][:3]
        attrs = ProductAttribute.objects.filter(product__is_active=True, attribute_value__isnull=False).select_related(
            'product', 'attribute_type', 'attribute_value').prefetch_related('product__gallery').order_by('pk')
        matched = []
        for attr in attrs:
            if q in attr.attribute_type.name.casefold() or q in attr.attribute_value.value.casefold():
                product = attr.product
                matched.append({'type': 'attribute',
                    'title': f'{attr.attribute_type.name}: {attr.attribute_value.value}',
                    'product_title': product.title, 'url': product.get_absolute_url(),
                    'image': cover(product), 'price': str(product.price) if product.price is not None else None,
                    'currency': product.currency})
                if len(matched) >= 5:
                    break
        if request:
            SearchService.save_query(query, request)
        # Не кешировать опубликованность: скрытый объект исчезает сразу.
        return (results[:10 - len(category_results)] + category_results + matched)[:10]

    @staticmethod
    def get_popular_queries(limit=10):
        from .models import SearchQuery
        from django.db.models import Sum

        return list(
            SearchQuery.objects
            .values('query')
            .annotate(total=Sum('count'))
            .order_by('-total')[:limit]
            .values_list('query', flat=True)
        )

    @staticmethod
    def save_query(query, request):
        if len(query) < 2:
            return
        if request.user.is_authenticated:
            obj, created = SearchQuery.objects.get_or_create(
                query=query,
                user=request.user,
                defaults={'count': 1}
            )
            if not created:
                obj.count += 1
                obj.save()
        else:
            history = request.session.get('search_history', [])
            if query in history:
                history.remove(query)
            history.insert(0, query)
            if len(history) > 10:
                history = history[:10]
            request.session['search_history'] = history
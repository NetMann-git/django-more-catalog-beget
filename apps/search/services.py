# apps/search/services.py

from django.core.cache import cache
from django.db.models import Q
from easy_thumbnails.files import get_thumbnailer
from apps.products.models import Product, Category, Badge, ProductAttribute
from .models import SearchQuery


class SearchService:
    LIMIT = 8

    @staticmethod
    def _thumbnail_url(image, size=(80, 120)):
        """Возвращает URL миниатюры для изображения."""
        if not image:
            return None
        try:
            thumbnail = get_thumbnailer(image).get_thumbnail({
                'size': size,
                'crop': True,
            })
            return thumbnail.url
        except Exception:
            return image.url

    @staticmethod
    def search(query):
        """
        Поиск товаров по запросу (для страницы результатов).
        """
        if not query:
            return []
        
        q = Q()
        q |= Q(title__icontains=query)
        q |= Q(article__icontains=query)
        q |= Q(short_description__icontains=query)
        q |= Q(description__icontains=query)
        
        return Product.objects.filter(q, is_active=True)

    @staticmethod
    def suggest(query, request=None):
        cache_key = f"search_suggest_{query.lower()}"
        results = cache.get(cache_key)
        if results is not None:
            return results

        # Нормализуем запрос (регистронезависимое сравнение)
        q = query.casefold()

        # 1. Товары – фильтрация в Python
        products = Product.objects.filter(is_active=True).select_related('category', 'brand').prefetch_related('badges')
        matched_products = []
        for product in products:
            if (q in (product.title or "").casefold() or
                q in (product.article or "").casefold() or
                q in (product.short_description or "").casefold() or
                q in (product.description or "").casefold()):
                matched_products.append(product)
            if len(matched_products) >= SearchService.LIMIT:
                break

        product_results = []
        for product in matched_products:
            product_results.append({
                'type': 'product',
                'id': product.id,
                'title': product.title,
                'price': str(product.price) if product.price is not None else None,
                'currency': product.currency,
                'url': product.get_absolute_url(),
                'image': SearchService._thumbnail_url(product.image),
                'badges': [{'title': b.title, 'slug': b.slug} for b in product.badges.all()],
                'category': product.category.title if product.category else None,
                'brand': product.brand.name if product.brand else None,
            })

        # 2. Категории – фильтрация в Python
        categories = Category.objects.all()
        matched_categories = []
        for cat in categories:
            if q in (cat.title or "").casefold():
                matched_categories.append(cat)
            if len(matched_categories) >= 3:
                break
        category_results = [
            {'type': 'category', 'title': c.title, 'url': '/catalog/?category=' + str(c.pk)}
            for c in matched_categories
        ]

        # 3. Бейджи – фильтрация в Python
        badges = Badge.objects.all()
        matched_badges = []
        for badge in badges:
            if q in (badge.title or "").casefold():
                matched_badges.append(badge)
            if len(matched_badges) >= 3:
                break
        badge_results = [
            {'type': 'badge', 'title': b.title, 'url': '/catalog/?badge=' + b.slug}
            for b in matched_badges
        ]

        # 4. Характеристики – фильтрация в Python
        attrs = ProductAttribute.objects.select_related('product', 'attribute_type', 'attribute_value').all()
        matched_attrs = []
        for attr in attrs:
            product = attr.product
            if not product or not product.is_active:
                continue
            if (q in (attr.attribute_type.name or "").casefold() or
                q in (attr.attribute_value.value or "").casefold()):
                matched_attrs.append(attr)
            if len(matched_attrs) >= 5:
                break

        attribute_results = []
        for attr in matched_attrs:
            product = attr.product
            attribute_results.append({
                'type': 'attribute',
                'title': f"{attr.attribute_type.name}: {attr.attribute_value.value}",
                'product_title': product.title,
                'url': product.get_absolute_url(),
                'image': SearchService._thumbnail_url(product.image),
                'price': str(product.price) if product.price is not None else None,
                'currency': product.currency,
            })

        # Собираем все результаты
        results = product_results + category_results + badge_results + attribute_results
        results = results[:10]

        cache.set(cache_key, results, 300)

        # Сохраняем историю
        if request:
            SearchService.save_query(query, request)

        return results

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
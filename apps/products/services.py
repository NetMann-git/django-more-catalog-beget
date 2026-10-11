# apps/products/services.py
from django.core.cache import cache

from .cache_keys import (
    CACHE_TIMEOUT,
    SIMILAR_PRODUCTS_PREFIX,
)
from .repository import CatalogRepository

from .session_service import SessionService
from apps.products.models import Product

from .constants import (
    ATTRIBUTE_COLLECTION,
    ATTRIBUTE_SILHOUETTE,
)

class ProductService:

    @staticmethod
    def get_recently_viewed_products(
        request,
        current_product=None,
    ):
        """
        Возвращает недавно просмотренные товары
        в порядке, заданном сессией.

        Если указан current_product,
        он исключается из результата.
        """

        recently_viewed = SessionService.get_recently_viewed(
            request,
        )

        recent_ids = recently_viewed

        if current_product:
            recent_ids = [
                product_id
                for product_id in recently_viewed
                if product_id != current_product.id
            ]

        products = Product.objects.filter(
            id__in=recent_ids,
            is_active=True,
        ).select_related('brand').prefetch_related('gallery')

        order = {
            product_id: index
            for index, product_id in enumerate(recently_viewed)
        }

        return sorted(
            products,
            key=lambda product: order.get(
                product.id,
                999,
            ),
        )


    @staticmethod
    def _extend_similar(similar, queryset, limit):
        """
        Добавляет товары в список similar,
        исключая уже найденные.
        """
        ids = [product.id for product in similar]

        similar.extend(
            queryset.exclude(id__in=ids)
            .distinct()[:limit - len(similar)]
        )

    @staticmethod
    def get_similar_products(product, limit=4):
        cache_key = f"{SIMILAR_PRODUCTS_PREFIX}{product.pk}"
        similar = cache.get(cache_key)
        if similar is None:
            queryset = CatalogRepository.related(product)
            similar = []

            # Получаем коллекцию и силуэт через ProductAttribute
            
            collection_value = ProductService._get_attribute_value(
                product,
                ATTRIBUTE_COLLECTION,
            )
            
            silhouette_value = ProductService._get_attribute_value(
                product,
                ATTRIBUTE_SILHOUETTE,
            )

            # 1. Та же коллекция + тот же силуэт
            if collection_value and silhouette_value:
                similar = list(
                    queryset.filter(
                        attributes__attribute_type__slug=ATTRIBUTE_COLLECTION,
                        attributes__attribute_value__value=collection_value,
                    ).filter(
                        attributes__attribute_type__slug=ATTRIBUTE_SILHOUETTE,
                        attributes__attribute_value__value=silhouette_value,
                    ).distinct()[:limit]
                )

            # 2. Та же коллекция
            if len(similar) < limit and collection_value:
                ProductService._extend_similar(
                    similar,
                    queryset.filter(
                        attributes__attribute_type__slug=ATTRIBUTE_COLLECTION,
                        attributes__attribute_value__value=collection_value,
                    ),
                    limit,
                )

            # 3. Тот же силуэт
            if len(similar) < limit and silhouette_value:
                ProductService._extend_similar(
                    similar,
                    queryset.filter(
                        attributes__attribute_type__slug=ATTRIBUTE_SILHOUETTE,
                        attributes__attribute_value__value=silhouette_value,
                    ),
                    limit,
                )

            # 4. Любые товары (запасной вариант)
            if len(similar) < limit:
                ProductService._extend_similar(
                    similar,
                    queryset,
                    limit,
                )

            cache.set(cache_key, similar, CACHE_TIMEOUT)
        return similar


    @staticmethod
    def _get_attribute_value(product, slug):
        """
        Возвращает значение характеристики товара по slug.
        """
        attribute = (
            product.attributes
            .filter(attribute_type__slug=slug)
            .select_related("attribute_value")
            .first()
        )
        return attribute.attribute_value.value if attribute else None
    
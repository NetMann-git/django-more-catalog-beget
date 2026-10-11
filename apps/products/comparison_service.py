# apps/products/comparison_service.py

from apps.products.models import Product, ProductAttribute

from .session_service import SessionService


class ComparisonService:
    """
    Сервис для работы со сравнением товаров.
    """

    @staticmethod
    def get_products(request):
        """
        Возвращает товары для сравнения
        в порядке, выбранном пользователем.
        """

        ids = SessionService.get_comparison(
            request,
        )

        products = Product.objects.filter(
            id__in=ids,
            is_active=True,
        ).select_related("brand").prefetch_related("gallery")

        order = {
            product_id: index
            for index, product_id in enumerate(ids)
        }

        return sorted(
            products,
            key=lambda product: order.get(
                product.id,
                999,
            ),
        )

    @staticmethod
    def get_attributes_rows(products):
        """Собрать все значения каждой характеристики одним запросом."""
        products = list(products)
        if not products:
            return []
        attributes_data = {}
        attributes = ProductAttribute.objects.filter(
            product_id__in=[product.pk for product in products]
        ).select_related('attribute_type', 'attribute_value').order_by(
            'attribute_type__name', 'sort_order', 'attribute_value__sort_order', 'pk'
        )
        for attr in attributes:
            values = attributes_data.setdefault(attr.attribute_type.name, {})
            selected = values.setdefault(attr.product_id, [])
            if attr.attribute_value_id:
                value = attr.attribute_value.value
                if value.strip() and value not in selected:
                    selected.append(value)
        rows = []
        for name, values in attributes_data.items():
            row = {'name': name}
            for product in products:
                selected = values.get(product.pk, [])
                row[product.pk] = '; '.join(selected) if selected else '—'
            rows.append(row)
        return rows

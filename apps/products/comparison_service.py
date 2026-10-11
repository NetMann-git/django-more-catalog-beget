# apps/products/comparison_service.py

from apps.products.models import Product

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
        """
        Формирует строки характеристик
        для таблицы сравнения.
        """

        attributes_data = {}

        for product in products:
            for attr in product.attributes.select_related(
                "attribute_type",
            ).all():
                key = attr.attribute_type.name

                if key not in attributes_data:
                    attributes_data[key] = {}

                attributes_data[key][product.id] = (
                    attr.attribute_value.value
                    if attr.attribute_value
                    else "—"
                )

        attributes_rows = []

        for attr_name, values in attributes_data.items():
            row = {
                "name": attr_name,
            }

            for product in products:
                row[product.id] = values.get(
                    product.id,
                    "—",
                )

            attributes_rows.append(row)

        return attributes_rows

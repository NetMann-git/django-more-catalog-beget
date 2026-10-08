"""Проверка и применение параметров фильтра каталога автомобилей."""

from decimal import Decimal, InvalidOperation

from django.db import connection
from django.db.models import F, Q
from django.db.models.functions import Lower

from apps.products.models import AttributeValue, Brand, ProductAttribute, Product


NUMERIC_ATTRIBUTES = {
    "mileage": "mileage",
    "engine_volume": "engine_volume",
    "power": "power",
}
FUEL_SLUGS = ("engine_type", "fuel_type")


def parse_number(value):
    """Разобрать число из справочника без приведения некорректных строк к нулю."""
    if value is None:
        return None
    try:
        number = Decimal(str(value).replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


class CatalogFilter:
    """Читает параметры GET и возвращает отфильтрованный queryset."""

    def __init__(self, request_get):
        self.query = request_get.get("q", "").strip()
        self.category = request_get.get("category", "")
        self.brand = request_get.get("brand", "")
        self.year = request_get.get("year", "")
        self.year_min = request_get.get("year_min", "")
        self.year_max = request_get.get("year_max", "")
        self.fuel_type = request_get.get("fuel_type", "")
        self.sort = request_get.get("sort", "")
        self.availability = request_get.get("availability", "")
        self.transmission = request_get.get("transmission", "")
        self.drive = request_get.get("drive", "")
        self.condition = request_get.get("condition", "")
        self.price_min = request_get.get("price_min", "")
        self.price_max = request_get.get("price_max", "")
        self.mileage_min = request_get.get("mileage_min", "")
        self.mileage_max = request_get.get("mileage_max", "")
        self.engine_volume_min = request_get.get("engine_volume_min", "")
        self.engine_volume_max = request_get.get("engine_volume_max", "")
        self.power_min = request_get.get("power_min", "")
        self.power_max = request_get.get("power_max", "")
        self.errors = []
        self.ranges = {}
        for field in ("price", "mileage", "engine_volume", "power"):
            lower_raw = getattr(self, f"{field}_min")
            upper_raw = getattr(self, f"{field}_max")
            lower = parse_number(lower_raw) if lower_raw else None
            upper = parse_number(upper_raw) if upper_raw else None
            if ((lower_raw and lower is None) or (upper_raw and upper is None)
                    or (lower is not None and upper is not None and lower > upper)):
                self.errors.append(f"Проверьте диапазон: {self._labels[field]}.")
            self.ranges[field] = (lower, upper)

    _labels = {
        "price": "цена", "mileage": "пробег",
        "engine_volume": "объём двигателя", "power": "мощность",
    }

    @staticmethod
    def _attribute_products(slug, value_ids):
        """Подзапрос по значению характеристики исключает дубликаты карточек."""
        return ProductAttribute.objects.filter(
            attribute_type__slug=slug,
            attribute_value_id__in=value_ids,
        ).values("product_id")

    def _numeric_products(self, slug, lower, upper):
        """Сравнивать справочные значения как Decimal, затем искать их товары."""
        values = AttributeValue.objects.filter(
            attribute_type__slug=slug,
        ).values_list("id", "value")
        matching = []
        for pk, raw_value in values:
            number = parse_number(raw_value)
            if (number is not None
                    and (lower is None or number >= lower)
                    and (upper is None or number <= upper)):
                matching.append(pk)
        return self._attribute_products(slug, matching)

    def apply(self, queryset):
        """Применить фильтры без текстовых сравнений числовых характеристик."""
        if self.errors:
            return queryset.none()
        if self.category:
            if self.category.isdigit():
                category_members = Product.categories.through.objects.filter(
                    category_id=self.category,
                ).values("product_id")
                queryset = queryset.filter(Q(category_id=self.category) | Q(pk__in=category_members))
            else:
                queryset = queryset.none()
        if self.brand:
            queryset = queryset.filter(brand_id=self.brand) if self.brand.isdigit() else queryset.none()
        if self.availability:
            queryset = queryset.filter(availability_status=self.availability)
        for key in ("transmission", "drive", "condition"):
            value = getattr(self, key)
            if value:
                queryset = queryset.filter(pk__in=ProductAttribute.objects.filter(
                    attribute_type__slug=key,
                    attribute_value__value=value,
                ).values("product_id"))
        if self.year:
            queryset = queryset.filter(pk__in=self._attribute_products(
                "year", AttributeValue.objects.filter(
                    attribute_type__slug="year", value=self.year,
                ).values("pk"),
            ))
        if self.year_min or self.year_max:
            lower = parse_number(self.year_min) if self.year_min else None
            upper = parse_number(self.year_max) if self.year_max else None
            if (self.year_min and lower is None) or (self.year_max and upper is None):
                return queryset.none()
            queryset = queryset.filter(pk__in=self._numeric_products(
                "year", lower, upper,
            ))
        if self.fuel_type:
            queryset = queryset.filter(pk__in=ProductAttribute.objects.filter(
                attribute_type__slug__in=FUEL_SLUGS,
                attribute_value_id=self.fuel_type,
            ).values("product_id")) if self.fuel_type.isdigit() else queryset.none()

        for field, (lower, upper) in self.ranges.items():
            if lower is None and upper is None:
                continue
            if field == "price":
                queryset = queryset.filter(currency="RUB")
                if lower is not None:
                    queryset = queryset.filter(price__gte=lower)
                if upper is not None:
                    queryset = queryset.filter(price__lte=upper)
            else:
                queryset = queryset.filter(pk__in=self._numeric_products(
                    NUMERIC_ATTRIBUTES[field], lower, upper,
                ))

        if self.query:
            if connection.vendor == "sqlite" and not self.query.isascii():
                # SQLite LIKE ignores case only for ASCII. Compare Unicode
                # titles in Python, preserving the remaining queryset filters.
                needle = self.query.casefold()
                matching_ids = [pk for pk, title in queryset.values_list("pk", "title")
                                if needle in title.casefold()]
                queryset = queryset.filter(pk__in=matching_ids)
            else:
                queryset = queryset.filter(title__icontains=self.query)

        if self.sort == "price_asc":
            queryset = queryset.order_by(F("price").asc(nulls_last=True), "pk")
        elif self.sort == "price_desc":
            queryset = queryset.order_by(F("price").desc(nulls_last=True), "pk")
        elif self.sort == "title_asc":
            queryset = queryset.order_by(Lower("title"), "pk")
        elif self.sort == "title_desc":
            queryset = queryset.order_by(Lower("title").desc(), "pk")
        elif self.sort == "year_desc":
            # Год приводится к числу при подборе значения, чтобы не сортировать текст.
            year_values = AttributeValue.objects.filter(
                attribute_type__slug="year",
            ).values_list("id", "value")
            from django.db.models import Case, IntegerField, Value, When
            years = {pk: int(number) for pk, value in year_values
                     if (number := parse_number(value)) is not None
                     and number == int(number)}
            if years:
                from django.db.models import OuterRef, Subquery
                year_ids = ProductAttribute.objects.filter(
                    product_id=OuterRef("pk"),
                    attribute_type__slug="year",
                ).values("attribute_value_id")[:1]
                queryset = queryset.annotate(_year_id=Subquery(year_ids)).annotate(
                    _catalog_year=Case(
                        *(When(_year_id=pk, then=Value(year)) for pk, year in years.items()),
                        default=Value(0), output_field=IntegerField(),
                    )
                ).order_by("-_catalog_year", "pk")
        return queryset

    def context(self):
        """Сохранить введённые значения после отправки формы."""
        result = {
            "search_query": self.query,
            "selected_brand": self.brand,
            "selected_brand_name": (
                Brand.objects.filter(pk=self.brand).values_list("name", flat=True).first()
                if self.brand.isdigit() else None
            ),
            "selected_category": self.category,
            "selected_year": self.year,
            "selected_fuel_type": self.fuel_type,
            "selected_fuel_name": (
                AttributeValue.objects.filter(pk=self.fuel_type)
                .values_list("value", flat=True).first()
                if self.fuel_type.isdigit() else None
            ),
            "selected_sort": self.sort,
            "filter_errors": self.errors,
        }
        for field in self.ranges:
            result[f"selected_{field}_min"] = getattr(self, f"{field}_min")
            result[f"selected_{field}_max"] = getattr(self, f"{field}_max")
        return result

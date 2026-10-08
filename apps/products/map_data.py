"""Координаты Joomla longlat: сохранять исходные строки без округления."""
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError


def coordinate_pair(value):
    if not value or not str(value).strip():
        return None
    parts = str(value).split(",")
    if len(parts) != 2:
        raise ValidationError("Введите долготу и широту через запятую, например 38.887676, 44.197811.")
    try:
        numbers = [Decimal(part.strip()) for part in parts]
    except InvalidOperation as exc:
        raise ValidationError("Координаты должны быть числами с точкой в дробной части.") from exc
    if not all(n.is_finite() for n in numbers) or not (-180 <= numbers[0] <= 180 and -90 <= numbers[1] <= 90):
        raise ValidationError("Долгота должна быть от −180 до 180, широта — от −90 до 90.")
    return [part.strip() for part in parts]


def validate_coordinates(value):
    coordinate_pair(value)


def product_map(product):
    """Не показывать карту без корректной метки; центр по умолчанию — метка."""
    try:
        marker = coordinate_pair(product.map_coordinates)
        if marker is None:
            return None
        center = coordinate_pair(product.map_center) or marker
    except ValidationError:
        return None
    zoom = product.map_zoom if product.map_zoom is not None else 12
    if not 0 <= zoom <= 19:
        return None
    params = urlencode({"ll": ",".join(center), "pt": ",".join(marker), "z": zoom})
    return {
        "marker": marker, "center": center, "zoom": zoom,
        "title": product.title, "address": product.address,
        "api_key": getattr(settings, "YANDEX_MAPS_API_KEY", ""),
        "url": "https://yandex.ru/maps/?" + params,
    }


def apply_map_import(product, source):
    """Подготовить поля из значения JBZoo; запись объекта выполняет импортёр."""
    if not isinstance(source, dict):
        raise ValidationError("Значение карты JBZoo должно быть словарём.")
    marker = source.get("location", "") or ""
    center = source.get("mapcenter", "") or ""
    raw_zoom = source.get("zoom", "")
    coordinate_pair(marker)
    coordinate_pair(center)
    try:
        zoom = None if raw_zoom in (None, "") else int(str(raw_zoom).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Некорректный масштаб карты в импорте.") from exc
    if zoom is not None and not 0 <= zoom <= 19:
        raise ValidationError("Масштаб карты должен быть от 0 до 19.")
    if len(str(marker)) > 255 or len(str(center)) > 255:
        raise ValidationError("Строка координат слишком длинная.")
    product.map_coordinates = str(marker)
    product.map_center = str(center)
    product.map_zoom = zoom
    product.map_source = dict(source)

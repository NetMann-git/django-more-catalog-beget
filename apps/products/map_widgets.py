"""Редактор карты с ручным вводом, доступным без API и JavaScript."""
from django import forms
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


class MapCoordinatesWidget(forms.TextInput):
    class Media:
        css = {"all": ("products/css/object-map.css",)}
        js = ("products/js/object-map.js",)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        field_id = attrs.get("id", "id_" + name)
        field = super().render(name, value, attrs, renderer)
        prefix = field_id.removesuffix("map_coordinates")
        controls = render_to_string("products/widgets/map_editor.html", {
            "marker_id": field_id, "center_id": prefix + "map_center",
            "zoom_id": prefix + "map_zoom",
            "api_key": getattr(settings, "YANDEX_MAPS_API_KEY", ""),
        })
        return mark_safe(str(field) + controls)

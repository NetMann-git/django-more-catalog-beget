"""HTML-редактор цен с резервным textarea без JavaScript."""
from django import forms
from django.utils.html import format_html
from .prices_html import sanitize_prices


class PricesWidget(forms.Textarea):
    class Media:
        css = {"all": ("products/css/prices-editor.css",)}
        js = ("products/js/prices-editor.js",)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        attrs["data-prices-editor"] = "true"
        textarea = super().render(name, value, attrs, renderer)
        return format_html(
            '{}<textarea hidden class="prices-editor__initial" aria-hidden="true">{}</textarea>',
            textarea, sanitize_prices(value or ""),
        )

"""Предпросмотр неопубликованного объекта и сохранённый путь Joomla."""
from django.shortcuts import get_object_or_404, redirect
from django.http import Http404
from urllib.parse import urlsplit
from django.views.decorators.cache import never_cache

from apps.users.decorators import role_required
from apps.users.constants import ROLE_MANAGER, ROLE_ADMIN
from .models import Product
from .views import product_detail


@never_cache
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def item_preview(request, product_id):
    product = get_object_or_404(Product, pk=product_id, joomla_id__isnull=False)
    return product_detail(request, product.slug, _import_preview=True)


def legacy_item(request, slug, prefix="properties-list"):
    product = get_object_or_404(Product, slug=slug, joomla_id__isnull=False, is_active=True)
    if urlsplit(product.joomla_url).path.replace("//", "/") != f"/{prefix}/{slug}.html":
        raise Http404
    return product_detail(request, product.slug)

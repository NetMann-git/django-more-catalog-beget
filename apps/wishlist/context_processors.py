"""Количество опубликованных объектов в избранном."""
from apps.products.public_lists import active_product_ids
from .models import Favorite


def wishlist_count(request):
    if request.user.is_authenticated:
        count = Favorite.objects.filter(user=request.user, product__is_active=True).count()
    else:
        count = len(active_product_ids(request.session.get('wishlist', [])))
    return {'wishlist_count': count}

# apps\wishlist\views.py

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from apps.products.public_lists import active_product_ids, unique_product_ids
from apps.products.models import Product
from .models import Favorite


class WishlistView(ListView):
    model = Favorite
    template_name = "wishlist/wishlist.html"
    context_object_name = "favorites"
    allow_empty = True

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Favorite.objects.filter(user=self.request.user, product__is_active=True).select_related("product", "product__brand").prefetch_related("product__gallery")
        return Favorite.objects.none()  # для гостей пустой queryset, товары будем брать из сессии

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            products = [favorite.product for favorite in context['favorites']]
            wishlist_ids = [product.pk for product in products]
        else:
            wishlist_ids = self.request.session.get('wishlist', [])
            by_id = {product.pk: product for product in
                     Product.objects.filter(pk__in=wishlist_ids, is_active=True)
                     .select_related('brand').prefetch_related('gallery')}
            products = [by_id[pk] for pk in reversed(list(dict.fromkeys(wishlist_ids)))
                        if pk in by_id]
            wishlist_ids = [product.pk for product in products]

        cards = []
        for product in products:
            gallery = list(product.gallery.all())
            cards.append({'product': product, 'cover': product.image or
                          (gallery[0].image if gallery else None)})
        context.update(products=products, cards=cards, wishlist_ids=wishlist_ids,
                       is_guest=not self.request.user.is_authenticated,
                       housing_public_page=True)

        return context


@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)

    if request.user.is_authenticated:
        favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)
        if not created:
            favorite.delete()
            is_favorite = False
        else:
            is_favorite = True
        count = Favorite.objects.filter(user=request.user, product__is_active=True).count()
    else:
        wishlist = unique_product_ids(request.session.get('wishlist', []))
        if product.id in wishlist:
            wishlist.remove(product.id)
            is_favorite = False
        else:
            wishlist.append(product.id)
            is_favorite = True
        request.session['wishlist'] = wishlist
        count = len(active_product_ids(wishlist))

    return JsonResponse({
        "is_favorite": is_favorite,
        "count": count,
    })


@require_POST
def clear_wishlist_ajax(request):
    """
    AJAX-очистка избранного.
    """
    if request.user.is_authenticated:
        Favorite.objects.filter(user=request.user).delete()
    else:
        request.session['wishlist'] = []
        request.session.modified = True

    return JsonResponse({
        "success": True,
        "count": 0,
    })
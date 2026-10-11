"""Похожие объекты жилья по публичной категории и исходному типу."""
from django.db.models import Q
from .category_views import public_tree
from .models import Product


def housing_cards(products):
    """Карточки с исходным главным фото или первой фотографией галереи."""
    cards = []
    for product in products:
        gallery = list(product.gallery.all())
        cards.append({'product': product, 'cover': product.image or
                      (gallery[0].image if gallery else None)})
    return cards


def related_housing(product, limit=4):
    """Сначала тот же тип в общей категории, затем категория, затем тип."""
    if limit <= 0:
        return []
    public_ids = {category.pk for category in public_tree()}
    categories = set(product.categories.values_list('pk', flat=True))
    if product.category_id:
        categories.add(product.category_id)
    categories &= public_ids
    base = Product.objects.filter(is_active=True).exclude(pk=product.pk).select_related('brand').prefetch_related('gallery').order_by('title', 'pk')
    groups = []
    if categories:
        same_category = base.filter(Q(category_id__in=categories) | Q(categories__pk__in=categories)).distinct()
        if product.brand_id:
            groups.append(same_category.filter(brand_id=product.brand_id))
        groups.append(same_category)
    if product.brand_id:
        groups.append(base.filter(brand_id=product.brand_id))
    result = []
    for group in groups:
        ids = [item.pk for item in result]
        result.extend(group.exclude(pk__in=ids)[:limit - len(result)])
        if len(result) == limit:
            break
    return result

from .housing_detail import housing_context
# apps/products/views.py

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from .constants import MAX_COMPARISON_ITEMS, MAX_RECENTLY_VIEWED
from .services import ProductService
from .context import CatalogContextBuilder

from django.urls import reverse
from apps.products.models import Brand

from apps.reviews.forms import ReviewForm

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ProductForm, GalleryImageForm, BrandForm
from .attribute_formsets import ManagerSingleAttributeFormSet
from .multiple_attribute_forms import build_multiple_form

from .models import Product, ProductGalleryImage, AttributeType, AttributeValue, ProductAttribute

from .repository import CatalogRepository

from apps.users.decorators import role_required
from apps.users.constants import ROLE_MANAGER, ROLE_ADMIN
from .cache import CatalogCache

from .session_service import SessionService

from apps.reviews.services import ReviewService

from .comparison_service import ComparisonService

from .context import ProductContextBuilder

from apps.recommendations.services import RecommendationService


def brand_detail(request, slug):
    brand = get_object_or_404(Brand, slug=slug)
    products = CatalogRepository.by_brand(brand)
    context = {
        'brand': brand,
        'products': products,
        'page': brand,  # для SEO (чтобы работал base.html)
    }
    return render(request, 'products/brand_detail.html', context)

@require_POST
def toggle_comparison_ajax(request, product_id):
    """
    AJAX-обработчик для добавления/удаления товара из сравнения.
    Возвращает JSON с новым состоянием и количеством товаров.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)
    comparison = SessionService.get_comparison(request)
    is_added = False

    if product_id in comparison:
        comparison = SessionService.remove_from_comparison(
            request,
            product_id,
        )
        message = f"Товар «{product.title}» удалён из сравнения."
    else:
        # Проверка лимита для AJAX
        if not SessionService.can_add_to_comparison(
            request,
            MAX_COMPARISON_ITEMS,
        ):
            return JsonResponse({
                'error': True,
                'message': f'Можно добавить не более {MAX_COMPARISON_ITEMS} товаров.'
            }, status=400)

        comparison = SessionService.add_to_comparison(
            request,
            product_id,
        )
        is_added = True
        message = f"Товар «{product.title}» добавлен к сравнению."

    count = len(comparison)

    return JsonResponse({
        'is_added': is_added,
        'count': count,
        'message': message,
    })


def catalog(request):
    context = CatalogContextBuilder.build(request)

    # AJAX-подгрузка товаров при прокрутке
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render(
            request,
            'products/_catalog_cards.html',
            context,
        ).content.decode('utf-8')

        page_obj = context['page_obj']
        return JsonResponse({
            'html': html,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        })

    return render(request, "products/catalog.html", context)

def recently_viewed_list(request):
    """
    Страница со списком всех просмотренных товаров + блок рекомендаций.
    """
    recently_ids = request.session.get('recently_viewed', [])
    products = Product.objects.filter(
        id__in=recently_ids, is_active=True
    ) if recently_ids else Product.objects.none()

    # Получаем рекомендации на основе просмотренных товаров
    recommended_products = RecommendationService.get_similar_products(
        products, limit=4
    )

    context = {
        'products': products,
        'recently_viewed_ids': recently_ids,
        'recommended_products': recommended_products,
    }
    return render(request, 'products/recently_viewed.html', context)

# @cache_page(60 * 5)  # 5 минут
def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("brand", "location"), slug=slug, is_active=True)
    context = {"product": product, "page": product}
    context.update(housing_context(product))
    context["car_order_success"] = (
        request.session.pop('car_order_success_product_id', None) == product.pk
    )

    if request.user.is_authenticated:
            wishlist_ids = list(request.user.favorites.values_list("product_id", flat=True))
    else:
            wishlist_ids = request.session.get('wishlist', [])
    context["wishlist_ids"] = wishlist_ids

    
    context["similar_products"] = (
        ProductService.get_similar_products(product)
    )
    
    # Сохраняем товар в список недавно просмотренных
    SessionService.save_recently_viewed(
        request,
        product.id,
        MAX_RECENTLY_VIEWED,
    )


    # Получаем товары для блока «Недавно просмотренные» (без текущего)
    context["recently_viewed_products"] = (
        ProductService.get_recently_viewed_products(
            request,
            product,
        )
    )

    # Отзывы – фильтрация и сортировка
    
    reviews_qs = ReviewService.get_reviews(
        product,
        request,
    )

    sort_by = request.GET.get(
        "sort",
        "-helpful_count",
    )


    rating_filter = request.GET.get("rating")
    with_photos = request.GET.get("with_photos")
    verified = request.GET.get("verified")   


    context["reviews"] = reviews_qs
    context["selected_sort"] = sort_by
    context["selected_rating"] = rating_filter
    context["selected_with_photos"] = with_photos
    context["selected_verified"] = verified

    # Варианты для шаблона
    context["sort_options"] = [
        {'value': '-helpful_count', 'label': 'Новые и полезные'},
        {'value': '-created_at', 'label': 'По дате (новые)'},
        {'value': '-rating', 'label': 'С высокой оценкой'},
        {'value': 'rating', 'label': 'С низкой оценкой'},

    ]
    context["rating_options"] = [
        {'value': '', 'label': 'Все оценки'},
        {'value': '5', 'label': '5 ★'},
        {'value': '4', 'label': '4 ★ и выше'},
        {'value': '3', 'label': '3 ★ и выше'},
    ]

    context["review_form"] = ReviewForm(user=request.user)

    return render(request, "products/product_detail.html", context)

@require_POST
def clear_recently_viewed_ajax(request):
    """
    AJAX-очистка истории просмотров.
    """
    # Удаляем ключ из сессии
    if 'recently_viewed' in request.session:
        del request.session['recently_viewed']
    # Явно помечаем сессию как изменённую
    request.session.modified = True
    return JsonResponse({'success': True, 'count': 0})

def add_to_comparison(request, product_id):
    """
    Добавляет товар в список сравнения.
    """
    product = get_object_or_404(
        Product,
        id=product_id,
        is_active=True,
    )

    comparison = SessionService.get_comparison(request)

    # Товар уже находится в сравнении
    if product_id in comparison:
        messages.info(
            request,
            f"Товар «{product.title}» уже в списке сравнения.",
        )

        return redirect(
            request.META.get(
                "HTTP_REFERER",
                "catalog:catalog",
            )
        )

    # Проверяем лимит ДО добавления товара
    if not SessionService.can_add_to_comparison(
        request,
        MAX_COMPARISON_ITEMS,
    ):
        messages.warning(
            request,
            f"Можно добавить не более "
            f"{MAX_COMPARISON_ITEMS} товаров для сравнения.",
        )

        return redirect(
            request.META.get(
                "HTTP_REFERER",
                "catalog:catalog",
            )
        )

    # Добавляем товар
    SessionService.add_to_comparison(
        request,
        product_id,
    )

    messages.success(
        request,
        f"Товар «{product.title}» добавлен к сравнению.",
    )

    return redirect(
        request.META.get(
            "HTTP_REFERER",
            "catalog:catalog",
        )
    )


def remove_from_comparison(request, product_id):
    comparison = SessionService.get_comparison(request)
    if product_id in comparison:
        comparison = SessionService.remove_from_comparison(
            request,
            product_id,
        )
        messages.success(request, "Товар удалён из сравнения.")
    return redirect(request.META.get('HTTP_REFERER', 'catalog:catalog'))


def comparison_list(request):
    products = ComparisonService.get_products(request)

    attributes_rows = ComparisonService.get_attributes_rows(
        products,
    )

    # Получаем рекомендации для страницы сравнения
    recommended_products = RecommendationService.get_similar_products(
        viewed_products=products,
        page='comparison',
        limit=4
    )

    context = {
        'products': products,
        'attributes_rows': attributes_rows,
        'recommended_products': recommended_products,
    }

    return render(
        request,
        'products/comparison.html',
        context,
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def brand_list_manage(request):
    """Список типов жилья для управления менеджером."""
    brands = Brand.objects.all().order_by("sort_order", "name")

    search = request.GET.get("search", "").strip()
    if search:
        brands = brands.filter(
            Q(name__icontains=search)
        )

    if request.method == "POST":
        for brand in brands:
            value = request.POST.get(f"sort_order_{brand.pk}")
            if value is None:
                continue
            try:
                sort_order = max(0, int(value))
            except (TypeError, ValueError):
                continue
            if brand.sort_order != sort_order:
                brand.sort_order = sort_order
                brand.save(update_fields=["sort_order"])

        CatalogCache.clear_catalog()
        messages.success(request, "Порядок типов жилья сохранён.")
        url = reverse("catalog:brand_list_manage")
        if search:
            url += f"?search={search}"
        return redirect(url)

    return render(
        request,
        "products/brand_manage_list.html",
        {
            "brands": brands,
            "search": search,
            "total": brands.count(),
        },
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def brand_create(request):
    """Создание типа жилья менеджером."""
    if request.method == "POST":
        form = BrandForm(request.POST, request.FILES)
        if form.is_valid():
            brand = form.save()
            CatalogCache.clear_catalog()
            messages.success(request, f'Тип жилья "{brand.name}" успешно создан.')
            return redirect("catalog:brand_edit", brand_id=brand.pk)
    else:
        form = BrandForm()

    return render(
        request,
        "products/brand_form.html",
        {"form": form, "title": "Добавление типа жилья"},
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def brand_edit(request, brand_id):
    """Редактирование типа жилья менеджером."""
    brand = get_object_or_404(Brand, pk=brand_id)

    if request.method == "POST":
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            form.save()
            CatalogCache.clear_catalog()
            messages.success(request, f'Тип жилья "{brand.name}" успешно обновлён.')
            return redirect("catalog:brand_edit", brand_id=brand.pk)
    else:
        form = BrandForm(instance=brand)

    return render(
        request,
        "products/brand_form.html",
        {"form": form, "brand": brand, "title": "Редактирование типа жилья"},
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def brand_delete(request, brand_id):
    """Удаление типа жилья менеджером."""
    brand = get_object_or_404(Brand, pk=brand_id)

    if request.method == "POST":
        name = brand.name
        brand.delete()
        CatalogCache.clear_catalog()
        messages.success(request, f'Тип жилья "{name}" удалён.')
        return redirect("catalog:brand_list_manage")

    return render(
        request,
        "products/brand_confirm_delete.html",
        {"brand": brand},
    )

@role_required(ROLE_MANAGER, ROLE_ADMIN)
def product_list_manage(request):
    """Список товаров для управления (менеджер)."""
    
    products = Product.objects.all().order_by('-id')  # ИСПРАВЛЕНО
    
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(title__icontains=search) |
            Q(article__icontains=search) |
            Q(category__title__icontains=search) |
            Q(categories__title__icontains=search)
        ).distinct()
    
    paginator = Paginator(products, 20)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    context = {
        'products': products_page,
        'search': search,
        'total': products.count(),
    }
    return render(request, 'products/manage_list.html', context)

@role_required(ROLE_MANAGER, ROLE_ADMIN)
def product_create(request):
    """Создание нового товара."""

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)

        if form.is_valid():
            product = form.save()

            CatalogCache.clear_catalog()

            messages.success(request, f'Товар "{product.title}" успешно создан!')
            return redirect('catalog:product_edit', product_id=product.id)
    else:
        form = ProductForm()

    context = {
        'form': form,
        'title': 'Создание товара',
    }
    return render(request, 'products/product_form.html', context)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def product_edit(request, product_id):
    """Редактирование товара."""
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)

        if form.is_valid():
            form.save()

            CatalogCache.clear_catalog()

            messages.success(request, f'Товар "{product.title}" успешно обновлён!')
            return redirect('catalog:product_edit', product_id=product.id)
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'title': 'Редактирование товара',
    }
    return render(request, 'products/product_form.html', context)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def product_delete(request, product_id):
    """Удаление товара."""

    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product_title = product.title

        product.delete()

        CatalogCache.clear_catalog()

        messages.success(request, f'Товар "{product_title}" удалён.')
        return redirect('catalog:product_list_manage')

    context = {
        'product': product,
    }

    return render(
        request,
        'products/product_confirm_delete.html',
        context,
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def gallery_add(request: HttpRequest, product_id: int) -> HttpResponse:
    """Validate selected images before appending them to the gallery."""
  
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        images = request.FILES.getlist('image')
        if not images:
            messages.error(request, 'Выберите хотя бы одну фотографию.')
            return redirect('catalog:product_edit', product_id=product.id)

        forms = []
        for image in images:
            form = GalleryImageForm(request.POST, {'image': image})
            if not form.is_valid():
                details = '; '.join(
                    str(error)
                    for errors in form.errors.values()
                    for error in errors
                )
                messages.error(
                    request,
                    f'Файл «{image.name}»: {details} '
                    'Фотографии не добавлены. Проверьте выбранные файлы.',
                )
                return redirect('catalog:product_edit', product_id=product.id)
            forms.append(form)

        with transaction.atomic():
            last_order = product.gallery.aggregate(value=Max('sort_order'))['value']
            next_order = (last_order if last_order is not None else -1) + 1
            for offset, form in enumerate(forms):
                gallery_image = form.save(commit=False)
                gallery_image.product = product
                gallery_image.sort_order = next_order + offset
                gallery_image.save()
        messages.success(request, f'Добавлено фотографий: {len(forms)}.')
    
    return redirect('catalog:product_edit', product_id=product.id)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def gallery_delete(request, image_id):
    """Удаление изображения из галереи."""
    
    image = get_object_or_404(ProductGalleryImage, id=image_id)
    product_id = image.product.id
    image.delete()
    messages.success(request, 'Изображение удалено из галереи.')
    
    return redirect('catalog:product_edit', product_id=product_id)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def product_attributes(request, product_id):
    """Управление характеристиками товара."""
    
    product = get_object_or_404(Product, id=product_id)
    formset = ManagerSingleAttributeFormSet(
        request.POST if request.method == 'POST' else None,
        instance=product,
        queryset=product.attributes.select_related(
            'attribute_type', 'attribute_value',
        ),
        prefix='attributes',
    )
    multiple_form = build_multiple_form()(
        request.POST if request.method == 'POST' else None,
        product=product, prefix='multiple',
    )
    # Обе формы проверяются до любых изменений, чтобы сохранить всё вместе.
    if request.method == 'POST':
        single_valid = formset.is_valid()
        multiple_valid = multiple_form.is_valid()
    else:
        single_valid = multiple_valid = False
    if single_valid and multiple_valid:
        with transaction.atomic():
            formset.save()
            multiple_form.save_multiple(product)
            transaction.on_commit(CatalogCache.clear_catalog)
        messages.success(request, 'Характеристики сохранены.')
        return redirect('catalog:product_attributes', product_id=product.id)
    return render(request, 'products/product_attributes.html', {
        'product': product,
        'formset': formset,
        'multiple_form': multiple_form,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def attribute_delete(request, attribute_id):
    """Удаление характеристики товара."""
    
    attribute = get_object_or_404(ProductAttribute, id=attribute_id)
    product_id = attribute.product.id
    attribute.delete()
    messages.success(request, 'Характеристика удалена.')
    
    return redirect('catalog:product_attributes', product_id=product_id)

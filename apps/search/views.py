# apps/search/views.py

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from .services import SearchService


def popular(request):
    """
    Возвращает топ-10 популярных запросов.
    """
    queries = SearchService.get_popular_queries(limit=10)
    return JsonResponse({'popular': queries})


@vary_on_headers('X-Requested-With')
def suggest(request):
    """
    AJAX-эндпоинт для автодополнения поиска.
    Возвращает JSON со списком товаров, категорий, бейджей.
    """
    query = request.GET.get('q', '').strip()[:120]
    if len(query) < 2:
        return JsonResponse({'results': []}, status=200)

    # Вызываем сервис
    results = SearchService.suggest(query, request)

    return JsonResponse({
        'query': query,
        'results': results,
    })


def search(request):
    """Публичные результаты поиска жилья со старыми адресами объектов."""
    search_query = request.GET.get('query', '').strip()[:120]
    queryset = SearchService.search(search_query).select_related('brand').prefetch_related('gallery')
    paginator = Paginator(queryset, 12)
    try:
        page = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    cards = []
    for product in page:
        gallery = list(product.gallery.all())
        cards.append({'product': product, 'cover': product.image or
                      (gallery[0].image if gallery else None)})
    return TemplateResponse(request, 'search/search.html', {
        'search_query': search_query, 'search_results': page,
        'cards': cards, 'housing_public_page': True,
    })

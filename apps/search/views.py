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
    """Общие результаты поиска жилья и материалов по каноническим адресам."""
    search_query = request.GET.get('query', '').strip()[:120]
    queryset = SearchService.combined_search(search_query)
    paginator = Paginator(queryset, 12)
    try:
        page = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    cards = []
    result_cards = []
    for row in page:
        obj = row['object']
        if row['kind'] == 'housing':
            gallery = list(obj.gallery.all())
            cover = obj.image or (gallery[0].image if gallery else None)
            cards.append({'product': obj, 'cover': cover})
            image_url = cover.url if cover else None
        else:
            image_url = obj.cover_url
        result_cards.append({**row, 'image_url': image_url})
    return TemplateResponse(request, 'search/search.html', {
        'search_query': search_query, 'search_results': page,
        'cards': cards, 'result_cards': result_cards, 'housing_public_page': True,
    })

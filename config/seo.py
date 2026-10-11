"""Правила индексации публичного каталога жилья и служебных страниц."""
from django.http import HttpResponse
from django.urls import reverse


PRIVATE_PREFIXES = (
    '/admin/', '/account/', '/catalog/manage/', '/catalog/create/',
    '/catalog/edit/', '/catalog/delete/', '/catalog/attributes/',
    '/catalog/attribute/',
)
NOINDEX_PREFIXES = PRIVATE_PREFIXES + (
    '/search/', '/wishlist/', '/catalog/comparison/',
    '/catalog/recently-viewed/', '/catalog/clear-recently-viewed-ajax/',
    '/appointments/', '/reviews/', '/recommendations/',
)
NOINDEX_PATHS = {'/catalog/', '/terms/', '/privacy/', '/consent/'}


class HousingIndexingMiddleware:
    """Согласовать HTML robots и HTTP-заголовок для непубличной выдачи."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        request.seo_noindex = (
            path in NOINDEX_PATHS or path.startswith(NOINDEX_PREFIXES) or
            (path == '/catalog/housing/' and any(request.GET.get(key, '').strip()
             for key in ('q', 'category', 'housing_type')))
        )
        response = self.get_response(request)
        if request.seo_noindex:
            response['X-Robots-Tag'] = 'noindex, follow'
        return response


def robots_txt(request):
    """Указать карту сайта текущего домена и закрыть служебные маршруты."""
    lines = ['User-agent: *']
    lines.extend('Disallow: ' + prefix for prefix in PRIVATE_PREFIXES)
    lines += ['', 'Sitemap: ' + request.build_absolute_uri(reverse('housing_sitemap')), '']
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')

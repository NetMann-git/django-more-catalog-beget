"""XML-карта публичных страниц жилья с каноническими адресами."""
from xml.etree.ElementTree import Element, SubElement, tostring

from django.http import HttpResponse
from django.urls import reverse

from apps.information.sitemap import public_information_paths
from .category_views import public_tree
from .models import Brand, Product


SITEMAP_NAMESPACE = 'http://www.sitemaps.org/schemas/sitemap/0.9'


def housing_sitemap(request):
    """Отдать только публичные страницы без сессионных данных и дублей URL."""
    paths = {reverse('home'), reverse('catalog:housing_catalog'),
             reverse('catalog:category_index')}
    paths.update(category.get_absolute_url() for category in public_tree())
    paths.update(brand.get_absolute_url() for brand in
                 Brand.objects.filter(products__is_active=True).distinct())
    paths.update(product.get_absolute_url() for product in
                 Product.objects.filter(is_active=True).only('pk', 'slug', 'joomla_id', 'joomla_url'))
    paths.update(public_information_paths())
    root = Element('urlset', {'xmlns': SITEMAP_NAMESPACE})
    for path in sorted(paths):
        node = SubElement(root, 'url')
        SubElement(node, 'loc').text = request.build_absolute_uri(path)
    return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True),
                        content_type='application/xml; charset=utf-8')

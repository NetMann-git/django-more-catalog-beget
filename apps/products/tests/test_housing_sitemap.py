from urllib.parse import urlsplit
from xml.etree.ElementTree import fromstring
from django.test import TestCase
from apps.products.models import Product, Category, Brand


class HousingSitemapTests(TestCase):
    def urls(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])
        root = fromstring(response.content)
        self.assertEqual(root.tag, '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset')
        return [element.text for element in root.findall('{*}url/{*}loc')]

    def test_published_objects_original_urls_and_types(self):
        brand = Brand.objects.create(name='Гостевые дома', slug='guest')
        unused = Brand.objects.create(name='Пустой тип', slug='empty')
        product = Product.objects.create(title='Орион', slug='orion', joomla_id=9701, joomla_url='https://old.example/properties-list/orion.html', brand=brand, price=None)
        hidden = Product.objects.create(title='Скрытый', slug='hidden', joomla_id=9702, is_active=False, brand=unused, price=None)
        urls = self.urls()
        self.assertIn('http://testserver'+product.get_absolute_url(), urls)
        self.assertIn('http://testserver'+brand.get_absolute_url(), urls)
        self.assertNotIn('http://testserver'+hidden.get_absolute_url(), urls)
        self.assertNotIn('http://testserver'+unused.get_absolute_url(), urls)
        self.assertTrue(all(url.startswith('http://testserver/') for url in urls))
        self.assertEqual(len(urls), len(set(urls)))
        product.is_active = False
        product.save()
        self.assertNotIn('http://testserver'+product.get_absolute_url(), self.urls())

    def test_visible_categories_and_private_pages(self):
        public = Category.objects.create(title='Курорт', slug='resort')
        hidden = Category.objects.create(title='Скрытая', slug='hidden', is_published=False)
        child = Category.objects.create(title='Дочерняя', slug='child', parent=hidden)
        paths = [urlsplit(url).path for url in self.urls()]
        self.assertIn(public.get_absolute_url(), paths)
        self.assertNotIn(hidden.get_absolute_url(), paths)
        self.assertNotIn(child.get_absolute_url(), paths)
        for path in ['/search/', '/wishlist/', '/catalog/', '/catalog/comparison/', '/catalog/recently-viewed/', '/account/login/', '/admin/']:
            self.assertNotIn(path, paths)

    def test_empty_catalog_and_host_scheme(self):
        urls = self.urls()
        self.assertEqual(set(urls), {'http://testserver/', 'http://testserver/catalog/housing/', 'http://testserver/catalog/categories/', 'http://testserver/information/', 'http://testserver/information/maps/'})
        response = self.client.get('/sitemap.xml', secure=True)
        urls = [e.text for e in fromstring(response.content).findall('{*}url/{*}loc')]
        self.assertTrue(all(url.startswith('https://testserver/') for url in urls))
        for url in urls:
            self.assertEqual(self.client.get(urlsplit(url).path).status_code, 200)

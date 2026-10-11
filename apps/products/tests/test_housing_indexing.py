from django.test import TestCase
from apps.products.models import Product, Category, Brand


class HousingIndexingTests(TestCase):
    def test_robots_current_domain_and_private_paths(self):
        response = self.client.get('/robots.txt', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertContains(response, 'Sitemap: https://testserver/sitemap.xml')
        self.assertContains(response, 'Disallow: /admin/')
        self.assertContains(response, 'Disallow: /catalog/manage/')
        self.assertNotContains(response, 'Disallow: /catalog/\n')
        self.assertNotContains(response, 'Disallow: /search/')

    def test_noindex_meta_and_header(self):
        for path in ['/search/', '/wishlist/', '/catalog/recently-viewed/', '/catalog/comparison/', '/account/login/', '/privacy/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
                self.assertContains(response, '<meta name="robots" content="noindex, follow">')
                self.assertNotContains(response, '<meta name="robots" content="index, follow">')
        response = self.client.get('/catalog/manage/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')

    def test_public_pages_and_filter_variants(self):
        category = Category.objects.create(title='Курорт', slug='resort')
        brand = Brand.objects.create(name='Гостевые дома', slug='guest')
        product = Product.objects.create(title='Дом', slug='house', price=None, category=category, brand=brand, joomla_id=9801)
        for path in ['/', '/catalog/housing/', '/catalog/categories/', category.get_absolute_url(), brand.get_absolute_url(), product.get_absolute_url()]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('X-Robots-Tag', response)
            self.assertContains(response, '<meta name="robots" content="index, follow">')
        response = self.client.get('/catalog/housing/', {'category': 'resort'})
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
        self.assertContains(response, '<meta name="robots" content="noindex, follow">')
        response = self.client.get('/catalog/housing/', {'page': 1})
        self.assertNotIn('X-Robots-Tag', response)

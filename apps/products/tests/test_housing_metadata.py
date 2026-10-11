from bs4 import BeautifulSoup
from django.test import TestCase
from apps.products.models import Product, Brand, Category


class HousingMetadataTests(TestCase):
    def head(self, path, params=None):
        response = self.client.get(path, params or {})
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, 'html.parser').head

    def test_product_plain_metadata_and_legacy_canonical(self):
        product = Product.objects.create(title='Дом', slug='house', joomla_id=9901, joomla_url='https://old.example/properties-list/house.html', price=None, meta_title='Дом & уют', short_description='<p>Отдых <strong>у моря</strong></p><script>bad()</script>')
        head = self.head(product.get_absolute_url(), {'utm_source': 'test'})
        self.assertEqual(head.find('meta', attrs={'name': 'description'})['content'], 'Отдых у моря')
        canonical = head.find_all('link', rel='canonical')
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]['href'], 'http://testserver'+product.get_absolute_url())
        self.assertEqual(head.find('meta', property='og:url')['content'], canonical[0]['href'])
        product.refresh_from_db()
        self.assertIn('<strong>', product.short_description)

    def test_type_meta_without_description_and_pagination(self):
        brand = Brand.objects.create(name='Гостевые дома', slug='guest', meta_description='Описание типа без основного описания')
        for number in range(13):
            Product.objects.create(title=f'Дом {number:02}', slug=f'house-{number}', price=None, brand=brand)
        head = self.head(brand.get_absolute_url(), {'page': 2, 'utm_source': 'test'})
        self.assertEqual(head.find('meta', attrs={'name': 'description'})['content'], brand.meta_description)
        self.assertEqual(len(head.find_all('link', rel='canonical')), 1)
        self.assertEqual(head.find('link', rel='canonical')['href'], 'http://testserver'+brand.get_absolute_url()+'?page=2')

    def test_category_single_canonical_and_noindex_pages(self):
        category = Category.objects.create(title='Курорт', slug='resort', meta_description='<p>Жильё &amp; отдых</p>')
        head = self.head(category.get_absolute_url())
        self.assertEqual(head.find('meta', attrs={'name': 'description'})['content'], 'Жильё & отдых')
        self.assertEqual(len(head.find_all('link', rel='canonical')), 1)
        for path in ['/search/', '/wishlist/', '/catalog/comparison/']:
            self.assertIsNone(self.head(path).find('link', rel='canonical'))

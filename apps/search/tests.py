from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product, ProductGalleryImage


class HousingSearchResultsTests(TestCase):
    def test_cyrillic_address_original_links_and_cover(self):
        product = Product.objects.create(title='Гостевой дом «Орион»', slug='orion', joomla_id=9301, price=None, address='Морская, 2б')
        ProductGalleryImage.objects.create(product=product, image='housing/original.jpg')
        Product.objects.create(title='Орион скрытый', slug='hidden', price=None, is_active=False)
        for query in ['орион', 'ОРИОН', 'морская']:
            response = self.client.get(reverse('search:search'), {'query': query})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, product.get_absolute_url())
            self.assertContains(response, '/media/housing/original.jpg')
            self.assertContains(response, 'housing-public-page')
            self.assertEqual(response.context['search_results'].paginator.count, 1)
            self.assertNotContains(response, 'Орион скрытый')

    def test_empty_missing_and_escaped_query(self):
        self.assertContains(self.client.get(reverse('search:search')), 'Введите название')
        self.assertContains(self.client.get(reverse('search:search'), {'query': 'нет такого жилья'}), 'объектов не найдено')
        response = self.client.get(reverse('search:search'), {'query': '<script>alert(1)</script>'})
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_pagination_keeps_query_and_stable_order(self):
        for number in range(13):
            Product.objects.create(title=f'Дом {number:02}', slug=f'house-{number}', price=None)
        response = self.client.get(reverse('search:search'), {'query': 'дом'})
        self.assertEqual(len(response.context['cards']), 12)
        self.assertContains(response, 'query=%D0%B4%D0%BE%D0%BC&amp;page=2')
        response = self.client.get(reverse('search:search'), {'query': 'дом', 'page': 2})
        self.assertEqual(response.context['cards'][0]['product'].title, 'Дом 12')

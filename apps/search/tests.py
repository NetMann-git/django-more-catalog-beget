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


class HousingSuggestionsTests(TestCase):
    def test_address_cover_and_hidden_changes(self):
        product = Product.objects.create(title='Дом', slug='house', joomla_id=9401, address='Морская', price=None)
        ProductGalleryImage.objects.create(product=product, image='housing/original.jpg')
        response = self.client.get('/search/suggest/', {'q': 'морская'}).json()
        item = response['results'][0]
        self.assertEqual(item['url'], product.get_absolute_url())
        self.assertEqual(item['image'], '/media/housing/original.jpg')
        product.is_active = False
        product.save()
        self.assertEqual(self.client.get('/search/suggest/', {'q': 'морская'}).json()['results'], [])

    def test_visible_category_urls_and_hidden_ancestors(self):
        from apps.products.models import Category
        visible = Category.objects.create(title='Морской курорт', slug='sea')
        hidden = Category.objects.create(title='Морской скрытый', slug='hidden', is_published=False)
        Category.objects.create(title='Морской дочерний', slug='child', parent=hidden)
        results = self.client.get('/search/suggest/', {'q': 'морской'}).json()['results']
        self.assertEqual(results, [{'type': 'category', 'title': visible.title, 'url': visible.get_absolute_url()}])

    def test_short_query_and_guest_history(self):
        self.assertEqual(self.client.get('/search/suggest/', {'q': 'а'}).json()['results'], [])
        self.client.get('/search/suggest/', {'q': '  море  '})
        self.assertEqual(self.client.session['search_history'][0], 'море')

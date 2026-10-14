from django.test import TestCase
from apps.products.models import Product, Category
from apps.information.models import InformationMaterial


class InformationSearchTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='Отдых у водопада', slug='house-waterfall', price=None)
        self.material = InformationMaterial.objects.create(joomla_id=22, kind='info', title='Водопады Сочи', slug='waterfalls', body='<p>Маршруты для отдыха</p>', is_active=True)
        InformationMaterial.objects.create(joomla_id=10001, kind='info', title='Водопады скрытые', slug='hidden-info', is_active=False)

    def test_combined_results_cyrillic_and_original_url(self):
        for query in ['водопад', 'ВОДОПАД']:
            response = self.client.get('/search/', {'query': query})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['search_results'].paginator.count, 2)
            self.assertContains(response, self.product.get_absolute_url())
            self.assertContains(response, self.material.get_absolute_url())
            self.assertContains(response, 'Информационный материал')
            self.assertContains(response, 'href="/search/"')
            self.assertNotContains(response, 'Водопады скрытые')
        response = self.client.get('/search/', {'query': 'маршруты'})
        self.assertEqual(response.context['search_results'].paginator.count, 1)

    def test_suggestions_reserve_space_and_hidden_change(self):
        Category.objects.create(title='Водопады курорта', slug='waterfalls-resort')
        for number in range(9):
            Product.objects.create(title=f'Водопады {number}', slug=f'house-{number}', price=None)
        results = self.client.get('/search/suggest/', {'q': 'водопад'}).json()['results']
        self.assertLessEqual(len(results), 10)
        self.assertTrue(any(item['type'] == 'information' and item['url'] == self.material.get_absolute_url() for item in results))
        self.assertTrue(any(item['type'] == 'product' for item in results))
        self.assertTrue(any(item['type'] == 'category' for item in results))
        self.material.is_active = False
        self.material.save()
        results = self.client.get('/search/suggest/', {'q': 'водопад'}).json()['results']
        self.assertFalse(any(item['type'] == 'information' for item in results))

    def test_combined_pagination_and_safe_title(self):
        for number in range(13):
            InformationMaterial.objects.create(joomla_id=11000+number, kind='info', title=f'Материал {number:02}', slug=f'info-{number}', is_active=True)
        response = self.client.get('/search/', {'query': 'Материал'})
        self.assertEqual(len(response.context['result_cards']), 12)
        response = self.client.get('/search/', {'query': 'Материал', 'page': 2})
        self.assertEqual(response.context['result_cards'][0]['object'].title, 'Материал 12')
        self.material.title = '<script>bad()</script> Водопады'
        self.material.save()
        response = self.client.get('/search/', {'query': 'водопады'})
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertContains(response, '&lt;script&gt;')

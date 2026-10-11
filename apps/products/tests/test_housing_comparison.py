from django.test import TestCase
from apps.products.models import Product, ProductGalleryImage


class HousingComparisonTests(TestCase):
    def setUp(self):
        self.first = Product.objects.create(title='Первый дом', slug='first-house', joomla_id=9201, price=None, rooms_description='<p>Два номера</p>', meals_description='Кухня', beach_distance_description='300 метров', price_description='<table><tr><td>1000</td></tr></table>')
        self.last = Product.objects.create(title='Второй дом', slug='last-house', joomla_id=9202, price=None)
        self.hidden = Product.objects.create(title='Скрытый дом', slug='hidden-house', is_active=False, price=None)

    def test_public_fields_order_original_photo_and_links(self):
        ProductGalleryImage.objects.create(product=self.first, image='housing/original.jpg')
        session = self.client.session
        session['comparison'] = [self.last.pk, self.hidden.pk, 999999, self.first.pk]
        session.save()
        response = self.client.get('/catalog/comparison/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.pk for p in response.context['products']], [self.last.pk, self.first.pk])
        for value in ['Два номера', 'Кухня', '300 метров', '/media/housing/original.jpg', self.first.get_absolute_url()+'#housing-prices', 'housing-public-page']:
            self.assertContains(response, value)
        for value in ['автомобил', 'Артикул', 'Наличие', 'Под заказ', self.hidden.title]:
            self.assertNotContains(response, value)
        self.assertContains(response, 'Уточнить в карточке')

    def test_empty_comparison_and_remove(self):
        response = self.client.get('/catalog/comparison/')
        self.assertContains(response, 'Какие объекты сравним?')
        url = f'/catalog/comparison/toggle/{self.first.pk}/'
        self.assertTrue(self.client.post(url).json()['is_added'])
        self.assertContains(self.client.get('/catalog/comparison/'), self.first.title)
        self.assertFalse(self.client.post(url).json()['is_added'])
        self.assertEqual(self.client.get('/catalog/comparison/').context['products'], [])

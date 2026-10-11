from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product, ProductGalleryImage


class HousingHistoryTests(TestCase):
    def setUp(self):
        self.first = Product.objects.create(title='Первый дом', slug='first-house', price=None, joomla_id=9001)
        self.last = Product.objects.create(title='Последний дом', slug='last-house', price=None, joomla_id=9002)
        self.hidden = Product.objects.create(title='Скрытый дом', slug='hidden-house', is_active=False, price=None)

    def history(self, ids):
        session = self.client.session
        session['recently_viewed'] = ids
        session.save()
        return self.client.get(reverse('catalog:recently_viewed'))

    def test_order_visibility_and_original_links(self):
        response = self.history([self.last.pk, self.hidden.pk, 999999, self.first.pk, self.last.pk])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.pk for p in response.context['products']], [self.last.pk, self.first.pk])
        self.assertContains(response, self.last.get_absolute_url())
        self.assertNotContains(response, self.hidden.title)
        self.assertContains(response, 'housing-public-page')
        self.assertNotContains(response, 'автомобил')
        self.assertNotContains(response, 'В наличии')
        self.assertNotContains(response, 'Под заказ')
        self.assertContains(response, 'compare-btn')
        self.assertContains(response, 'wishlist-btn')
        self.assertContains(response, 'href="/catalog/housing/"')

    def test_empty_history_and_clear(self):
        response = self.history([])
        self.assertContains(response, 'Здесь появятся просмотренные объекты жилья')
        self.history([self.first.pk])
        response = self.client.post(reverse('catalog:clear_recently_viewed_ajax'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('recently_viewed', []), [])

    def test_original_gallery_cover(self):
        ProductGalleryImage.objects.create(product=self.first, image='housing/original.jpg')
        response = self.history([self.first.pk])
        self.assertContains(response, '/media/housing/original.jpg')
        self.assertNotContains(response, '/thumbnails/')

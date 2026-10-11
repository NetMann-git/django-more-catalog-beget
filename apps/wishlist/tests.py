from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.products.models import Product, ProductGalleryImage
from .models import Favorite


class HousingWishlistTests(TestCase):
    def setUp(self):
        self.first = Product.objects.create(title='Первый дом', slug='first-house', price=None, joomla_id=9101)
        self.last = Product.objects.create(title='Последний дом', slug='last-house', price=None, joomla_id=9102)
        self.hidden = Product.objects.create(title='Скрытый дом', slug='hidden-house', price=None, is_active=False)

    def test_guest_order_visibility_and_original_cover(self):
        ProductGalleryImage.objects.create(product=self.first, image='housing/original.jpg')
        session = self.client.session
        session['wishlist'] = [self.first.pk, self.hidden.pk, 999999, self.last.pk]
        session.save()
        response = self.client.get('/wishlist/')
        self.assertEqual([p.pk for p in response.context['products']], [self.last.pk, self.first.pk])
        self.assertContains(response, self.first.get_absolute_url())
        self.assertContains(response, '/media/housing/original.jpg')
        self.assertContains(response, 'housing-public-page')
        self.assertContains(response, 'href="/catalog/housing/"')
        self.assertNotContains(response, self.hidden.title)
        self.assertNotContains(response, 'автомобил')
        self.assertNotContains(response, 'Под заказ')
        self.assertContains(response, 'wishlist-btn active')
        self.assertContains(response, 'compare-btn')

    def test_authenticated_hidden_favorites_preserved(self):
        user = get_user_model().objects.create_user(username='guest-test', password='test-password')
        Favorite.objects.create(user=user, product=self.first)
        Favorite.objects.create(user=user, product=self.hidden)
        Favorite.objects.create(user=user, product=self.last)
        self.client.force_login(user)
        response = self.client.get('/wishlist/')
        self.assertEqual([p.pk for p in response.context['products']], [self.last.pk, self.first.pk])
        self.assertEqual(Favorite.objects.filter(user=user).count(), 3)
        self.assertNotContains(response, self.hidden.title)
        self.assertNotContains(response, 'как гость')
        self.client.post('/wishlist/clear/')
        self.assertFalse(Favorite.objects.filter(user=user).exists())

    def test_guest_toggle_remove_and_clear(self):
        self.assertEqual(self.client.post(f'/wishlist/toggle/{self.first.pk}/').json()['count'], 1)
        self.assertContains(self.client.get('/wishlist/'), self.first.title)
        self.assertFalse(self.client.post(f'/wishlist/toggle/{self.first.pk}/').json()['is_favorite'])
        response = self.client.get('/wishlist/')
        self.assertEqual(response.context['products'], [])
        self.assertContains(response, 'Здесь будут ваши избранные объекты жилья')
        self.client.post(f'/wishlist/toggle/{self.first.pk}/')
        self.assertTrue(self.client.post('/wishlist/clear/').json()['success'])
        self.assertEqual(self.client.session['wishlist'], [])

from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.products.models import Product
from apps.wishlist.models import Favorite
from apps.products.public_lists import active_product_ids


class PublicListCountsTests(TestCase):
    def setUp(self):
        self.visible = Product.objects.create(title='Дом', slug='house', price=None)
        self.hidden = Product.objects.create(title='Скрытый', slug='hidden', price=None, is_active=False)

    def test_header_counts_match_visible_lists(self):
        session = self.client.session
        ids = [self.hidden.pk, 999999, self.visible.pk, self.visible.pk]
        for key in ['wishlist', 'comparison', 'recently_viewed']:
            session[key] = ids
        session.save()
        for path in ['/wishlist/', '/catalog/comparison/', '/catalog/recently-viewed/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['wishlist_count'], 1)
            self.assertEqual(response.context['comparison_ids'], [self.visible.pk])
            self.assertEqual(response.context['recently_viewed_ids'], [self.visible.pk])
        self.assertEqual(self.client.session['wishlist'], ids)

    def test_comparison_stale_ids_do_not_fill_limit(self):
        session = self.client.session
        session['comparison'] = [self.hidden.pk, 999999, 999998, 999997]
        session.save()
        response = self.client.post(f'/catalog/comparison/toggle/{self.visible.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(self.client.session['comparison'], [self.visible.pk])
        for number in range(4):
            product = Product.objects.create(title=f'Дом {number}', slug=f'house-{number}', price=None)
            response = self.client.post(f'/catalog/comparison/toggle/{product.pk}/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.client.session['comparison']), 4)

    def test_wishlist_ajax_count_and_hidden_records_preserved(self):
        user = get_user_model().objects.create_user(username='test-count', password='test-password')
        Favorite.objects.create(user=user, product=self.hidden)
        self.client.force_login(user)
        response = self.client.post(f'/wishlist/toggle/{self.visible.pk}/')
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(self.client.get('/wishlist/').context['wishlist_count'], 1)
        self.assertTrue(Favorite.objects.filter(user=user, product=self.hidden).exists())
        self.client.logout()
        session = self.client.session
        session['wishlist'] = [self.hidden.pk, 999999]
        session.save()
        response = self.client.post(f'/wishlist/toggle/{self.visible.pk}/')
        self.assertEqual(response.json()['count'], 1)
        self.assertIn(self.hidden.pk, self.client.session['wishlist'])

    def test_ids_normalized_without_reordering(self):
        self.assertEqual(active_product_ids([None, True, {}, str(self.visible.pk), self.visible.pk, self.hidden.pk]), [self.visible.pk])

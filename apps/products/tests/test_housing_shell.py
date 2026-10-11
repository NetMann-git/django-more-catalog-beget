"""Страницы жилья не показывают контакты автокаталога и сохраняют функции карточки."""
from django.test import TestCase
from apps.home.models import ContactSettings
from apps.products.models import Product, Category


class HousingShellTests(TestCase):
    def setUp(self):
        self.contacts = ContactSettings.objects.update_or_create(pk=1, defaults={'phone_primary': '+79999990000', 'address': 'СТАРЫЙ АВТООФИС', 'map_url': 'https://yandex.ru/map-widget/old-car-office', 'is_published': True})[0]
        self.category = Category.objects.create(title='Побережье', slug='coast')
        self.product = Product.objects.create(title='Гостевой дом', slug='house', category=self.category, price=None, contact_phone='+79180001122', contact_name='Владелец')

    def test_home_catalog_index_category_and_object_use_housing_shell(self):
        for path in ['/', '/catalog/housing/', '/catalog/categories/', self.category.get_absolute_url(), self.product.get_absolute_url()]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'housing-public-page')
                self.assertContains(response, 'Категории жилья')
                self.assertNotContains(response, 'СТАРЫЙ АВТООФИС')
                self.assertNotContains(response, 'old-car-office')
                self.assertNotContains(response, '+79999990000')
                self.assertNotContains(response, 'href="/catalog/" class="nav-link')

    def test_owner_contacts_and_existing_navigation_preserved(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, '+79180001122')
        self.assertContains(response, 'Контакты и бронирование')
        self.assertContains(response, '/catalog/comparison/')
        self.assertContains(response, '/wishlist/')
        self.assertContains(response, '/catalog/recently-viewed/')
        self.assertContains(response, '/account/login/')
        self.contacts.refresh_from_db()
        self.assertEqual(self.contacts.address, 'СТАРЫЙ АВТООФИС')

    def test_category_menu_active_for_categories_only(self):
        self.assertContains(self.client.get('/catalog/categories/'), 'class="nav-link is-active">Категории жилья')
        self.assertContains(self.client.get(self.category.get_absolute_url()), 'class="nav-link is-active">Категории жилья')
        self.assertNotContains(self.client.get('/catalog/housing/'), 'class="nav-link is-active">Категории жилья')

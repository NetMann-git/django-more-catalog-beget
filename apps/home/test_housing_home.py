"""Главная подключена к жилью и показывает только опубликованные данные."""
from django.test import TestCase
from apps.products.models import Category, Brand, Product, ProductGalleryImage


class HousingHomeTests(TestCase):
    def setUp(self):
        self.region = Category.objects.create(title='Адлер', slug='adler-otdyh-s-cenami', joomla_id=73)
        self.brand = Brand.objects.create(name='Гостевые дома', slug='guest-houses')
        self.obj = Product.objects.create(title='Орион', slug='orion', category=self.region, brand=self.brand, joomla_id=1806, joomla_url='https://example.com/properties-list/orion.html', price=None)

    def test_form_links_and_count(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'action="/catalog/housing/"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="housing_type"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, '/properties-list/orion.html')
        self.assertContains(response, self.region.get_absolute_url())
        self.assertEqual(response.context['housing_count'], 1)
        self.assertNotContains(response, 'Готовим новый каталог')

    def test_hidden_objects_regions_and_types_not_exposed(self):
        self.obj.is_active = False
        self.obj.save()
        self.region.is_published = False
        self.region.save()
        response = self.client.get('/')
        self.assertEqual(response.context['housing_count'], 0)
        self.assertEqual(response.context['housing_home_types'], [])
        self.assertNotContains(response, self.obj.title)
        self.assertNotContains(response, self.region.get_absolute_url())
        self.assertContains(response, 'Опубликованные объекты пока не добавлены')

    def test_latest_six_and_secondary_gallery_cover(self):
        ProductGalleryImage.objects.create(product=self.obj, image='jbzoo/1806/images/uploads/user_606/606u11.jpg')
        self.assertContains(self.client.get('/'), '/media/jbzoo/1806/images/uploads/user_606/606u11.jpg')
        latest = [Product.objects.create(title=f'Дом {i}', slug=f'house-{i}', price=None) for i in range(8)]
        response = self.client.get('/')
        self.assertEqual(response.context['housing_count'], 9)
        self.assertEqual([card['product'].pk for card in response.context['housing_home_cards']], [p.pk for p in reversed(latest[-6:])])

    def test_form_conditions_open_housing_filter(self):
        response = self.client.get('/catalog/housing/', {'category': self.region.slug, 'housing_type': self.brand.slug, 'q': 'орион'})
        self.assertEqual(list(response.context['page_obj']), [self.obj])

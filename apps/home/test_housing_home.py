"""Главная подключена к жилью и показывает только опубликованные данные."""
from django.test import TestCase
from django.urls import reverse
from apps.information.models import InformationMaterial
from apps.products.models import Category, Brand, Product, ProductGalleryImage


class HousingHomeTests(TestCase):
    def setUp(self):
        self.region = Category.objects.create(title='Адлер', slug='adler-otdyh-s-cenami', joomla_id=73)
        self.brand = Brand.objects.create(name='Гостевые дома', slug='guest-houses')
        self.obj = Product.objects.create(title='Орион', slug='orion', category=self.region, brand=self.brand, joomla_id=1806, joomla_url='https://example.com/properties-list/orion.html', price=None)

    def test_form_and_catalog_links(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'action="/catalog/housing/"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="housing_type"')
        self.assertContains(response, 'name="view" value="map"')
        self.assertContains(response, '/properties-list/orion.html')
        self.assertContains(response, f'?category={self.region.slug}')
        self.assertContains(response, 'Цена по запросу')
        self.assertIn('csrftoken', response.cookies)
        self.assertNotContains(response, 'Готовим новый каталог')

    def test_hidden_objects_regions_and_types_not_exposed(self):
        self.obj.is_active = False
        self.obj.save()
        self.region.is_published = False
        self.region.save()
        response = self.client.get('/')
        self.assertEqual(response.context['housing_home_types'], [])
        self.assertNotContains(response, self.obj.title)
        self.assertNotContains(response, self.region.slug)
        self.assertContains(response, 'Опубликованные объекты пока не добавлены')

    def test_latest_six_and_secondary_gallery_cover(self):
        ProductGalleryImage.objects.create(product=self.obj, image='jbzoo/1806/images/uploads/user_606/606u11.jpg')
        self.assertContains(self.client.get('/'), '/media/jbzoo/1806/images/uploads/user_606/606u11.jpg')
        latest = [Product.objects.create(title=f'Дом {i}', slug=f'house-{i}', price=None) for i in range(8)]
        response = self.client.get('/')
        self.assertEqual([card['product'].pk for card in response.context['housing_home_cards']], [p.pk for p in reversed(latest[-6:])])

    def test_form_conditions_open_housing_filter(self):
        response = self.client.get('/catalog/housing/', {'category': self.region.slug, 'housing_type': self.brand.slug, 'q': 'орион'})
        self.assertEqual(list(response.context['page_obj']), [self.obj])

    def test_map_button_opens_selected_resort_and_type(self):
        self.obj.map_coordinates = '39.9,43.4'
        self.obj.save()
        resort_map = InformationMaterial.objects.create(
            title='Карта Адлера', slug='map-adler', joomla_id=836, kind='map', is_active=True,
        )
        InformationMaterial.objects.create(
            title='Карта Сочи', slug='map-sochi', joomla_id=841, kind='map', is_active=True,
        )
        response = self.client.get('/', {
            'view': 'map', 'category': self.region.slug, 'housing_type': self.brand.slug,
        })
        target = resort_map.get_absolute_url() + f'?type={self.brand.pk}'
        self.assertRedirects(response, target + '#housing-resort-map')
        self.assertContains(self.client.get(target), f'value="{self.brand.pk}" selected')

        resort_map.is_active = False
        resort_map.save()
        fallback = self.client.get('/', {'view': 'map', 'category': self.region.slug})
        self.assertRedirects(fallback, reverse('information:maps'))
        general = self.client.get('/', {'view': 'map'})
        self.assertIn('karta-sochi', general.url)

    def test_map_button_falls_back_to_map_index(self):
        response = self.client.get('/', {'view': 'map', 'category': self.region.slug})
        self.assertRedirects(response, reverse('information:maps'))

    def test_map_keeps_type_with_no_matching_points(self):
        Product.objects.create(
            title='Дом на карте', slug='map-home', category=self.region,
            map_coordinates='39.9,43.4',
        )
        resort_map = InformationMaterial.objects.create(
            title='Карта Адлера', slug='map-adler', joomla_id=836, kind='map', is_active=True,
        )
        response = self.client.get(resort_map.get_absolute_url(), {'type': self.brand.pk})
        self.assertContains(response, f'value="{self.brand.pk}" selected')
        self.assertContains(response, 'Гостевые дома (0)')

    def test_home_wishlist_button_uses_existing_session(self):
        client = self.client_class(enforce_csrf_checks=True)
        home = client.get('/')
        url = reverse('wishlist:toggle', args=[self.obj.pk])
        response = client.post(url, HTTP_X_CSRFTOKEN=home.cookies['csrftoken'].value)
        self.assertTrue(response.json()['is_favorite'])
        self.assertContains(client.get('/'), 'class="wishlist-btn active"')

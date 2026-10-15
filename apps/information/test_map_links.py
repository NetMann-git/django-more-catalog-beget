from django.test import TestCase
from apps.products.models import Category, Product
from .models import InformationMaterial
from .maps import product_map_links


class MapLinkTests(TestCase):
    def setUp(self):
        self.region = Category.objects.create(title='Адлер', slug='adler', joomla_id=73)
        self.child = Category.objects.create(title='Номера', slug='rooms', parent=self.region)
        self.product = Product.objects.create(title='<Дом>', slug='house', is_active=True,
            map_coordinates='39.9,43.4', map_center='bad')
        self.product.categories.add(self.child)
        self.material = InformationMaterial.objects.create(title='Карта', slug='map', kind='map',
            map_mode='categories', is_active=True)
        self.material.map_categories.add(self.region)

    def test_links_use_actual_scope_and_do_not_depend_on_center(self):
        links = product_map_links(self.product)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['url'], self.material.get_absolute_url()+f'?object={self.product.pk}#housing-resort-map')
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, 'Жильё рядом на карте')
        self.assertContains(response, links[0]['url'])
        self.region.is_published = False; self.region.save()
        self.assertEqual(product_map_links(self.product), [])

    def test_missing_coordinates_hidden_material_or_product_have_no_links(self):
        self.product.map_coordinates = ''; self.product.save()
        self.assertEqual(product_map_links(self.product), [])
        self.product.map_coordinates = 'NaN,43'; self.product.save()
        self.assertEqual(product_map_links(self.product), [])
        self.product.map_coordinates = '39,43'; self.product.save()
        self.material.is_active = False; self.material.save()
        self.assertEqual(product_map_links(self.product), [])
        self.material.is_active = True; self.material.save()
        self.product.is_active = False; self.product.save()
        self.assertEqual(product_map_links(self.product), [])

    def test_selection_is_limited_to_public_points_and_canonical_omits_query(self):
        response = self.client.get(self.material.get_absolute_url(), {'object': self.product.pk})
        self.assertContains(response, 'Выбранный объект:')
        self.assertContains(response, '&lt;Дом&gt;')
        self.assertEqual(response.context['map_data']['selected_id'], self.product.pk)
        self.assertContains(response, 'href="http://testserver'+self.material.get_absolute_url()+'"', count=None)
        alien = Product.objects.create(title='Секретное название', slug='hidden', is_active=False, map_coordinates='39,43')
        for value in (alien.pk, 'NaN', '9'*100, '<script>', 999999):
            response = self.client.get(self.material.get_absolute_url(), {'object': value})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context['map_data']['selected_id'])
            self.assertNotContains(response, 'Секретное название')
            self.assertNotContains(response, 'Выбранный объект:')
        self.product.categories.clear()
        response = self.client.get(self.material.get_absolute_url(), {'object': self.product.pk})
        self.assertIsNone(response.context['map_data']['selected_id'])

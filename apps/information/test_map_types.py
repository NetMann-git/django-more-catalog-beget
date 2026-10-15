from django.test import TestCase
from apps.products.models import Brand, Category, Product
from .maps import material_map
from .models import InformationMaterial


class MapTypeTests(TestCase):
    def test_types_come_only_from_public_points_and_query_count_is_bounded(self):
        cat = Category.objects.create(title='Курорт', slug='resort')
        m = InformationMaterial.objects.create(title='Карта', slug='map', kind='map', map_mode='categories', is_active=True)
        m.map_categories.add(cat)
        house = Brand.objects.create(name='<Гостевой дом>', slug='house', sort_order=1)
        flat = Brand.objects.create(name='Квартира', slug='flat', sort_order=2)
        hidden_type = Brand.objects.create(name='Скрытый тип', slug='hidden-type')
        for i, brand in enumerate((house, house, flat, None)):
            Product.objects.create(title='Объект '+str(i), slug='obj-'+str(i), brand=brand, category=cat,
                                   map_coordinates='39,43', is_active=True)
        Product.objects.create(title='Скрытый объект', slug='hidden', brand=hidden_type, category=cat,
                               map_coordinates='39,43', is_active=False)
        Product.objects.create(title='Без метки', slug='no-marker', brand=hidden_type, category=cat, is_active=True)
        with self.assertNumQueries(3):
            data = material_map(m)
        self.assertEqual([row['value'] for row in data['housing_types']], [str(house.pk), str(flat.pk), 'untyped'])
        self.assertEqual([row['count'] for row in data['housing_types']], [2, 1, 1])
        self.assertEqual(data['points'][0]['housing_type'], str(house.pk))
        self.assertEqual(sum(row['count'] for row in data['housing_types']), len(data['points']))
        response = self.client.get(m.get_absolute_url())
        self.assertContains(response, 'id="information-map-type"')
        self.assertContains(response, '&lt;Гостевой дом&gt; (2)')
        self.assertContains(response, 'Тип не указан (1)')
        self.assertNotContains(response, 'Скрытый тип')

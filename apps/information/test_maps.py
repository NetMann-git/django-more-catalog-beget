from django.test import TestCase
from apps.products.models import Category, Product
from .maps import material_map, MAP_REGIONS
from .models import InformationMaterial


class MaterialMapTests(TestCase):
    def test_category_scope_coordinates_and_publication(self):
        region = Category.objects.create(title='Адлер', slug='adler', joomla_id=73)
        child = Category.objects.create(title='Номера', slug='rooms', parent=region)
        other = Category.objects.create(title='Туапсе', slug='tuapse', joomla_id=86)
        material = InformationMaterial.objects.create(title='Карта', slug='map', joomla_id=836, kind='map', is_active=True)
        good = Product.objects.create(title='<Дом>', slug='house', category=other, is_active=True,
                                      map_coordinates='39.9,43.4', map_center='bad')
        good.categories.add(child, region)
        Product.objects.create(title='Чужой', slug='other', category=other, is_active=True, map_coordinates='39,44')
        Product.objects.create(title='Скрытый', slug='hidden', category=region, is_active=False, map_coordinates='39,44')
        Product.objects.create(title='Ошибка', slug='bad', category=region, is_active=True, map_coordinates='NaN,44')
        data = material_map(material)
        self.assertEqual([p['title'] for p in data['points']], ['<Дом>'])
        self.assertEqual(data['points'][0]['coordinates'], ['39.9', '43.4'])
        response = self.client.get(material.get_absolute_url())
        self.assertContains(response, 'information-map-data')
        self.assertContains(response, '&lt;Дом&gt;')
        self.assertNotContains(response, '<Дом>')
        self.assertContains(response, good.get_absolute_url())
        region.is_published = False; region.save()
        self.assertEqual(material_map(material)['points'], [])

    def test_explicit_regions_and_unknown_material(self):
        self.assertEqual(len(MAP_REGIONS), 10)
        self.assertNotIn(84, MAP_REGIONS[841])
        self.assertNotIn(86, MAP_REGIONS[841])
        self.assertIsNone(material_map(InformationMaterial(joomla_id=1, kind='map')))
        self.assertIsNone(material_map(InformationMaterial(joomla_id=836, kind='info')))

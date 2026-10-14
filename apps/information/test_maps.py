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


class ConfigurableMapTests(TestCase):
    def test_custom_scope_can_replace_legacy_and_be_empty(self):
        a = Category.objects.create(title='Адлер', slug='a', joomla_id=73)
        b = Category.objects.create(title='Туапсе', slug='b', joomla_id=86)
        child = Category.objects.create(title='Дочерняя', slug='child', parent=b)
        Product.objects.create(title='Адлер', slug='adler', category=a, is_active=True, map_coordinates='39,43')
        Product.objects.create(title='Туапсе', slug='tuapse', category=child, is_active=True, map_coordinates='38,44')
        m = InformationMaterial.objects.create(title='Карта', slug='custom', joomla_id=836, kind='map')
        self.assertEqual(material_map(m)['points'][0]['title'], 'Адлер')
        m.map_mode = 'categories'; m.save()
        self.assertEqual(material_map(m)['points'], [])
        m.map_categories.add(b)
        self.assertEqual([p['title'] for p in material_map(m)['points']], ['Туапсе'])
        m.map_categories.clear()
        self.assertEqual(material_map(m)['points'], [])
        m.kind = 'info'; m.save()
        self.assertIsNone(material_map(m))

    def test_admin_creates_new_material_without_joomla_id(self):
        from django.contrib.auth import get_user_model
        from .models import InformationCategory
        user = get_user_model().objects.create_superuser(username='editor', email='editor@example.org', password='testpass')
        self.client.force_login(user)
        cat = Category.objects.create(title='Курорт', slug='resort')
        Product.objects.create(title='Дом', slug='home', category=cat, is_active=True, map_coordinates='39,43')
        response = self.client.get('/admin/information/informationmaterial/add/')
        self.assertContains(response, 'id_map_categories')
        response = self.client.post('/admin/information/informationmaterial/add/', {
            'title': 'Новая карта', 'slug': 'new-map', 'kind': 'map', 'is_active': 'on',
            'map_mode': 'categories', 'map_categories': [cat.pk], '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        m = InformationMaterial.objects.get(slug='new-map')
        self.assertIsNone(m.joomla_id)
        self.assertEqual(material_map(m)['points'][0]['title'], 'Дом')
        self.assertContains(self.client.get(m.get_absolute_url()), 'information-map-data')
        InformationMaterial.objects.create(title='Ещё материал', slug='another', kind='info')
        c = InformationCategory(title='Новая категория', slug='new-category')
        c.full_clean(); c.save()
        self.assertIsNone(c.joomla_id)

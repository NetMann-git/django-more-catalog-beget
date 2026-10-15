from django.test import TestCase
from apps.products.models import Category
from apps.products.category_views import public_tree
from .models import InformationMaterial
from .map_navigation import category_map_links, map_category_links


class MapNavigationTests(TestCase):
    def setUp(self):
        self.region = Category.objects.create(title='Адлер', slug='adler', joomla_id=73)
        self.child = Category.objects.create(title='Гостевые дома', slug='houses', parent=self.region)
        self.other = Category.objects.create(title='Туапсе', slug='tuapse', joomla_id=86)
        self.map = InformationMaterial.objects.create(title='Карта Адлера', slug='map-adler',
            joomla_id=836, kind='map', is_active=True)

    def test_category_and_descendant_link_to_map_with_public_backlink(self):
        for category in (self.region, self.child):
            response = self.client.get(category.get_absolute_url())
            self.assertContains(response, self.map.get_absolute_url()+'#housing-resort-map')
            self.assertContains(response, 'Посмотреть жильё на карте')
        response = self.client.get(self.map.get_absolute_url())
        self.assertContains(response, 'Категории жилья этой карты')
        self.assertContains(response, self.region.get_absolute_url())
        self.assertEqual(map_category_links(self.map), [{'title': self.region.title, 'url': self.region.get_absolute_url()}])
        self.assertEqual(category_map_links(self.other), [])

    def test_custom_map_hidden_parent_and_hidden_material(self):
        self.map.map_mode = 'categories'; self.map.save()
        self.map.map_categories.add(self.child)
        self.assertEqual(category_map_links(self.region), [])
        self.assertEqual(len(category_map_links(self.child)), 1)
        self.assertEqual(map_category_links(self.map)[0]['title'], self.child.title)
        self.region.is_published = False; self.region.save()
        self.assertEqual(category_map_links(self.child), [])
        self.assertEqual(map_category_links(self.map), [])
        self.region.is_published = True; self.region.save()
        self.map.is_active = False; self.map.save()
        self.assertEqual(category_map_links(self.child), [])

    def test_query_count_does_not_grow_with_number_of_maps(self):
        for i in range(6):
            m = InformationMaterial.objects.create(title='Карта '+str(i), slug='custom-'+str(i),
                kind='map', map_mode='categories', is_active=True)
            m.map_categories.add(self.region)
        categories = public_tree()
        with self.assertNumQueries(2):
            links = category_map_links(self.child, categories)
        self.assertEqual(len(links), 7)

from django.test import TestCase
from .models import InformationCategory, InformationMaterial
from .related import related_materials
from .views import public_categories


class RelatedMaterialTests(TestCase):
    def setUp(self):
        self.category = InformationCategory.objects.create(title='Природа', slug='nature')
        self.hidden = InformationCategory.objects.create(title='Скрытая', slug='hidden', is_published=False)
        self.child = InformationCategory.objects.create(title='Дочерняя скрытой', slug='hidden-child', parent=self.hidden)
        self.current = self.material('current', primary_category=self.category)

    def material(self, slug, **values):
        defaults = dict(title=slug, slug=slug, kind='info', is_active=True)
        defaults.update(values)
        return InformationMaterial.objects.create(**defaults)

    def related(self):
        return related_materials(self.current, {row.pk for row in public_categories()})

    def test_shared_primary_and_multiple_categories_no_duplicates_and_limit(self):
        for i in range(5):
            item = self.material('candidate-'+str(i), primary_category=self.category)
            item.categories.add(self.category)
        self.material('hidden', primary_category=self.category, is_active=False)
        self.material('map', primary_category=self.category, kind='map')
        self.material('unrelated')
        rows = self.related()
        self.assertEqual([row.slug for row in rows], ['candidate-0','candidate-1','candidate-2'])
        self.assertNotIn(self.current, rows)
        self.assertIn('source', rows[0].get_deferred_fields())
        response = self.client.get(self.current.get_absolute_url())
        self.assertContains(response, 'Другие материалы по теме')
        self.assertContains(response, rows[0].get_absolute_url())

    def test_hidden_parent_and_no_random_fallback(self):
        self.current.primary_category = self.child; self.current.save()
        self.material('same-hidden', primary_category=self.child)
        self.material('public-elsewhere', primary_category=self.category)
        self.assertEqual(self.related(), [])
        self.assertNotContains(self.client.get(self.current.get_absolute_url()), 'id="info-related-title"')
        self.current.primary_category = None; self.current.save()
        self.assertEqual(self.related(), [])

    def test_map_stays_with_maps_and_escapes_title(self):
        self.current.kind='map';self.current.save()
        other = self.material('other-map', kind='map', primary_category=self.category, title='<Карта>')
        self.material('article', primary_category=self.category)
        self.assertEqual(self.related(), [other])
        response = self.client.get(self.current.get_absolute_url())
        self.assertContains(response,'Другие карты')
        self.assertContains(response,'&lt;Карта&gt;')
        self.assertNotContains(response,'<Карта>')

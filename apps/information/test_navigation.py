from django.test import TestCase
from django.urls import reverse
from .models import InformationCategory, InformationMaterial
from .navigation import category_path


class InformationNavigationTests(TestCase):
    def setUp(self):
        self.root = InformationCategory.objects.create(title='Природа', slug='nature')
        self.child = InformationCategory.objects.create(title='Маршруты', slug='routes', parent=self.root)
        self.leaf = InformationCategory.objects.create(title='<Водопады>', slug='waterfalls', parent=self.child)
        self.other = InformationCategory.objects.create(title='Другое', slug='other')
        self.material = InformationMaterial.objects.create(title='Материал', slug='article', kind='info',
            is_active=True, primary_category=self.leaf)
        self.material.categories.add(self.other)

    def test_primary_path_and_primary_only_category_link(self):
        response = self.client.get(self.material.get_absolute_url())
        self.assertEqual(list(response.context['material_breadcrumb_categories']), [self.root,self.child,self.leaf])
        self.assertEqual(set(response.context['material_categories']), {self.leaf,self.other})
        self.assertContains(response, '&lt;Водопады&gt;')
        self.assertNotContains(response, '<Водопады>')
        self.assertContains(response, reverse('information:category',args=[self.leaf.slug]))
        self.assertEqual(self.material.categories.count(),1)

    def test_list_ancestors_children_and_search_query(self):
        response = self.client.get(reverse('information:category',args=[self.child.slug]), {'q':'водопад'})
        self.assertEqual(response.context['category_ancestors'], [self.root])
        self.assertEqual(response.context['subcategories'], [self.leaf])
        self.assertContains(response, 'Подкатегории материалов')
        self.assertContains(response, reverse('information:category',args=[self.leaf.slug])+'?q=')
        self.assertContains(response,'aria-current="page"')

    def test_hidden_ancestor_or_no_primary_does_not_choose_alternative(self):
        self.root.is_published=False;self.root.save()
        response = self.client.get(self.material.get_absolute_url())
        self.assertEqual(response.context['material_breadcrumb_categories'], [])
        self.assertEqual(list(response.context['material_categories']), [self.other])
        self.assertNotContains(response,'Природа')
        self.assertNotContains(response,'Маршруты')
        self.material.primary_category=None;self.material.save()
        response = self.client.get(self.material.get_absolute_url())
        self.assertEqual(response.context['material_breadcrumb_categories'], [])
        self.assertEqual(list(response.context['material_categories']), [self.other])

    def test_cycle_is_rejected_without_partial_path(self):
        InformationCategory.objects.filter(pk=self.root.pk).update(parent=self.leaf)
        self.root.refresh_from_db()
        self.assertEqual(category_path(self.leaf.pk,[self.root,self.child,self.leaf]), [])

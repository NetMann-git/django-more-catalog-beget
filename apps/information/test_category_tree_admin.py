from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from .models import InformationCategory, InformationMaterial


class InformationCategoryTreeTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(username='info-tree',password='test-password')
        self.client.force_login(user)
        self.root = InformationCategory.objects.create(title='Корень',slug='root',sort_order=2)
        self.child = InformationCategory.objects.create(title='<Дочерняя>',slug='child',parent=self.root)
        self.leaf = InformationCategory.objects.create(title='Внук',slug='leaf',parent=self.child)
        self.other = InformationCategory.objects.create(title='Другой корень',slug='other',sort_order=1,is_published=False)
        self.url=reverse('admin:information_informationcategory_changelist')

    def test_tree_correct_edit_links_and_direct_unique_counts(self):
        material = InformationMaterial.objects.create(title='Материал',slug='article',kind='info',is_active=True,primary_category=self.child)
        material.categories.add(self.child,self.root)
        InformationMaterial.objects.create(title='Скрытая карта',slug='hidden-map',kind='map',is_active=False,primary_category=self.child)
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        rows=response.context['cl'].result_list
        self.assertEqual([r.pk for r in rows],[self.other.pk,self.root.pk,self.child.pk,self.leaf.pk])
        self.assertEqual([r.tree_depth for r in rows],[0,0,1,2])
        self.assertEqual([r.elements_count for r in rows],[0,1,2,0])
        self.assertContains(response,reverse('admin:information_informationcategory_change',args=[self.child.pk]))
        self.assertContains(response,'&lt;Дочерняя&gt;')
        self.assertContains(response,'Свернуть всё')
        self.assertContains(response,'category-tree.js')
        self.assertContains(response,'Элементы')

    def test_search_publication_filter_and_permissions(self):
        response=self.client.get(self.url,{'q':'Внук'})
        rows=response.context['cl'].result_list
        self.assertEqual([r.pk for r in rows],[self.leaf.pk])
        self.assertEqual(rows[0].tree_depth,0)
        response=self.client.get(self.url,{'is_published__exact':'0'})
        self.assertEqual([r.pk for r in response.context['cl'].result_list],[self.other.pk])
        response=self.client.get(reverse('admin:autocomplete'),{
            'app_label':'information','model_name':'informationcategory','field_name':'parent','term':'Корень'})
        self.assertEqual(response.status_code,200)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)

    def test_cycle_validation_in_model_and_admin_form(self):
        self.root.parent=self.leaf
        with self.assertRaises(ValidationError):self.root.full_clean()
        self.child.parent=self.child
        with self.assertRaises(ValidationError):self.child.full_clean()
        response=self.client.post(reverse('admin:information_informationcategory_change',args=[self.root.pk]),{
            'title':self.root.title,'slug':self.root.slug,'parent':self.leaf.pk,'sort_order':'2','is_published':'on','_save':'Сохранить'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Категории не могут образовывать цикл.')
        self.root.refresh_from_db()
        self.assertIsNone(self.root.parent_id)

    def test_existing_corrupt_cycle_stays_visible_once(self):
        InformationCategory.objects.filter(pk=self.root.pk).update(parent=self.leaf)
        response=self.client.get(self.url)
        ids=[r.pk for r in response.context['cl'].result_list]
        self.assertEqual(set(ids),{self.root.pk,self.child.pk,self.leaf.pk,self.other.pk})
        self.assertEqual(len(ids),4)

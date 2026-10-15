from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import InformationCategory, InformationMaterial


class AdminMaterialCategoryFilterTests(TestCase):
    def setUp(self):
        user=get_user_model().objects.create_superuser(username='category-filter',password='test-password')
        self.client.force_login(user)
        self.root=InformationCategory.objects.create(title='Корень',slug='root')
        self.child=InformationCategory.objects.create(title='Дочерняя',slug='child',parent=self.root)
        self.leaf=InformationCategory.objects.create(title='Внук',slug='leaf',parent=self.child)
        self.direct=self.material('direct',primary_category=self.root)
        self.both=self.material('both',primary_category=self.child)
        self.both.categories.add(self.child)
        self.deep=self.material('deep',primary_category=self.leaf)
        self.hidden=self.material('hidden',primary_category=self.child,is_active=False,kind='map')
        self.unassigned=self.material('unassigned')
        self.url=reverse('admin:information_informationmaterial_changelist')

    def material(self,slug,**values):
        defaults=dict(title=slug,slug=slug,kind='info',is_active=True);defaults.update(values)
        return InformationMaterial.objects.create(**defaults)

    def ids(self,params):
        response=self.client.get(self.url,params)
        self.assertEqual(response.status_code,200)
        return {row.pk for row in response.context['cl'].result_list}

    def test_direct_and_tree_cover_fk_and_m2m_without_duplicates(self):
        self.assertEqual(self.ids({'material_category':self.child.pk,'category_scope':'direct'}),{self.both.pk,self.hidden.pk})
        self.assertEqual(self.ids({'material_category':self.child.pk}),{self.both.pk,self.hidden.pk,self.deep.pk})
        self.assertEqual(self.ids({'material_category':self.root.pk}),{self.direct.pk,self.both.pk,self.hidden.pk,self.deep.pk})
        response=self.client.get(self.url,{'material_category':self.child.pk})
        self.assertEqual(response.context['cl'].result_count,3)

    def test_count_link_opens_exact_direct_list(self):
        response=self.client.get(reverse('admin:information_informationcategory_changelist'))
        href=self.url+'?'+urlencode({'material_category':self.child.pk,'category_scope':'direct'})
        self.assertContains(response,href.replace('&','&amp;'))
        count=next(row.elements_count for row in response.context['cl'].result_list if row.pk==self.child.pk)
        self.assertEqual(len(self.ids({'material_category':self.child.pk,'category_scope':'direct'})),count)

    def test_unassigned_invalid_and_standard_filters(self):
        self.assertEqual(self.ids({'material_category':'none'}),{self.unassigned.pk})
        for value in ('-1','9999999','NaN','9'*100):
            self.assertEqual(self.ids({'material_category':value}),set())
        self.assertEqual(self.ids({'material_category':self.root.pk,'is_active__exact':'0'}),{self.hidden.pk})
        self.assertEqual(self.ids({'material_category':self.root.pk,'kind__exact':'map'}),{self.hidden.pk})
        self.assertEqual(self.ids({'material_category':self.root.pk,'q':'deep'}),{self.deep.pk})

    def test_hidden_category_remains_available_to_admin_and_cycle_terminates(self):
        self.child.is_published=False;self.child.save()
        self.assertEqual(self.ids({'material_category':self.child.pk}),{self.both.pk,self.hidden.pk,self.deep.pk})
        InformationCategory.objects.filter(pk=self.root.pk).update(parent=self.leaf)
        self.assertEqual(self.ids({'material_category':self.root.pk}),{self.direct.pk,self.both.pk,self.hidden.pk,self.deep.pk})
        self.client.logout()
        self.assertEqual(self.client.get(self.url,{'material_category':self.root.pk}).status_code,302)

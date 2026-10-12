from django.test import TestCase
from django.urls import reverse
from bs4 import BeautifulSoup
from .models import InformationMaterial, InformationCategory
from .legacy_urls import LEGACY_MATERIAL_PATHS


class InformationPublicTests(TestCase):
    def material(self, **kwargs):
        return InformationMaterial.objects.create(joomla_id=22, kind='info', title='Водопады', slug='waterfalls', is_active=True, **kwargs)

    def test_legacy_url_safe_html_and_original_unchanged(self):
        body='<p>Текст <strong>материала</strong></p><script>bad()</script>{tab Фото|warning}{module 117}{/tabs}'
        obj=self.material(body=body, source={'private_note':'NEVER_PUBLIC'})
        response=self.client.get(obj.get_absolute_url())
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'<strong>материала</strong>')
        self.assertContains(response,'Этот дополнительный блок пока недоступен.')
        self.assertNotContains(response,'<script>bad()</script>')
        self.assertNotContains(response,'{module 117}')
        self.assertNotContains(response,'NEVER_PUBLIC')
        head=BeautifulSoup(response.content,'html.parser').head
        self.assertEqual(head.find('link',rel='canonical')['href'],'http://testserver'+obj.get_absolute_url())
        obj.refresh_from_db();self.assertEqual(obj.body,body)

    def test_hidden_and_alias_redirect(self):
        obj=self.material()
        response=self.client.get(reverse('information:material',args=[obj.slug]))
        self.assertEqual(response.status_code,301)
        self.assertEqual(response['Location'],obj.get_absolute_url())
        obj.is_active=False;obj.save()
        self.assertEqual(self.client.get(obj.get_absolute_url()).status_code,404)
        self.assertNotContains(self.client.get('/information/'),obj.title)

    def test_category_multiple_memberships_and_hidden_ancestor(self):
        category=InformationCategory.objects.create(joomla_id=1,title='Курорт',slug='resort')
        hidden=InformationCategory.objects.create(joomla_id=2,title='Скрытая',slug='hidden',is_published=False)
        child=InformationCategory.objects.create(joomla_id=3,title='Дочерняя',slug='child',parent=hidden)
        obj=self.material();obj.categories.add(category,child)
        response=self.client.get(reverse('information:category',args=[category.slug]))
        self.assertContains(response,obj.title)
        self.assertNotContains(response,child.title)
        self.assertEqual(self.client.get(reverse('information:category',args=[child.slug])).status_code,404)

    def test_pagination_and_maps(self):
        for number in range(13):
            InformationMaterial.objects.create(joomla_id=10000+number,kind='info',title=f'Материал {number:02}',slug=f'article-{number}',is_active=True)
        InformationMaterial.objects.create(joomla_id=20000,kind='map',title='Карта',slug='map-test',is_active=True)
        response=self.client.get('/information/')
        self.assertEqual(len(response.context['page_obj']),12)
        self.assertEqual(response.context['page_obj'].paginator.count,14)
        self.assertEqual(self.client.get('/information/?page=3').status_code,404)
        response=self.client.get('/information/maps/')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertContains(response,'Карта')

    def test_missing_image_note_and_unknown_material(self):
        obj=self.material(body='<img src="images/no-file.jpg" alt="Фото">')
        response=self.client.get(obj.get_absolute_url())
        self.assertContains(response,'Изображение пока недоступно.')
        self.assertNotContains(response,'src="/images/no-file.jpg"')
        self.assertEqual(self.client.get('/information/material/not-found/').status_code,404)

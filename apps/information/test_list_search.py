from urllib.parse import urlencode
from django.test import TestCase
from django.urls import reverse
from .models import InformationCategory, InformationMaterial


class InformationListSearchTests(TestCase):
    def create_material(self, slug, **values):
        return InformationMaterial.objects.create(title='Водопады '+slug, slug=slug, kind='info', is_active=True, **values)

    def test_scoped_search_descendants_hidden_and_maps(self):
        parent = InformationCategory.objects.create(title='Природа', slug='nature')
        child = InformationCategory.objects.create(title='Маршруты', slug='routes', parent=parent)
        one = self.create_material('one', primary_category=child)
        one.categories.add(parent, child)
        self.create_material('outside')
        hidden = self.create_material('hidden', primary_category=parent)
        hidden.is_active = False; hidden.save()
        response = self.client.get(reverse('information:category', args=[parent.slug]), {'q':'ВОДОПАДЫ'})
        self.assertEqual(list(response.context['page_obj']), [one])
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
        self.assertContains(response, 'noindex, follow')
        self.assertNotContains(response, 'rel="canonical"')
        m = self.create_material('map');m.kind='map';m.save()
        response = self.client.get(reverse('information:maps'), {'q':'водопады'})
        self.assertEqual(list(response.context['page_obj']), [m])

    def test_pagination_and_scope_links_preserve_query_and_reset(self):
        for i in range(13):self.create_material('waterfall-'+str(i))
        url = reverse('information:index')
        response = self.client.get(url, {'q':'водопады'})
        self.assertEqual(response.context['page_obj'].paginator.count,13)
        self.assertContains(response, '?'+urlencode({'q':'водопады'})+'&amp;page=2')
        self.assertContains(response, reverse('information:maps')+'?'+urlencode({'q':'водопады'}))
        second = self.client.get(url, {'q':'водопады','page':2})
        self.assertEqual(len(second.context['page_obj']),1)
        clean = self.client.get(url)
        self.assertNotIn('X-Robots-Tag', clean)
        self.assertContains(clean, 'rel="canonical"')

    def test_validation_empty_results_and_escaping(self):
        self.create_material('one')
        url = reverse('information:index')
        response = self.client.get(url, {'q':'x'*201})
        self.assertContains(response,'Введите запрос длиной не более 200 символов.')
        self.assertEqual(response.context['page_obj'].paginator.count,0)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
        response = self.client.get(url, {'q':'<script>alert(1)</script>'})
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertContains(response, 'ничего не найдено')
        response = self.client.get(url, {'q':'   '})
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertNotIn('X-Robots-Tag',response)

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from .models import InformationMaterial


class MaterialPreviewTests(TestCase):
    def setUp(self):
        self.material = InformationMaterial.objects.create(title='Скрытый материал', slug='hidden-preview', body='<table><tr><td>Цена 700</td></tr></table><script>alert(1)</script>', source={'original': 'unchanged'})
        self.url = reverse('admin:information_informationmaterial_preview', args=[self.material.pk])
        self.user = get_user_model().objects.create_user(username='preview-staff', is_staff=True)

    def grant(self, codename):
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='information', codename=codename))
        self.client.force_login(self.user)

    def test_hidden_preview_is_private_safe_and_does_not_publish(self):
        self.grant('view_informationmaterial')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Цена 700')
        self.assertContains(response, 'материал не опубликован')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, 'noindex, follow')
        self.assertNotContains(response, 'rel="canonical"')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get(self.material.get_absolute_url()).status_code, 404)
        self.material.refresh_from_db()
        self.assertFalse(self.material.is_active)
        self.assertEqual(self.material.source, {'original': 'unchanged'})
        self.assertIn('<script>alert(1)</script>', self.material.body)

    def test_access_requires_staff_and_model_permission(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.user.is_staff = False
        self.user.save()
        self.grant('view_informationmaterial')
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_change_permission_and_missing_object(self):
        self.grant('change_informationmaterial')
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:information_informationmaterial_preview', args=[999999])).status_code, 404)

    def test_published_preview_and_admin_links(self):
        self.material.is_active = True
        self.material.save()
        self.grant('view_informationmaterial')
        self.assertContains(self.client.get(self.url), 'опубликованный материал')
        self.assertContains(self.client.get(reverse('admin:information_informationmaterial_changelist')), self.url)
        self.assertContains(self.client.get(reverse('admin:information_informationmaterial_change', args=[self.material.pk])), self.url)

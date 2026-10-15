from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse
from .models import InformationCategory, InformationMaterial


class SaveMaterialPreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='save-preview', is_staff=True)
        self.material = InformationMaterial.objects.create(title='До правки', slug='save-preview', kind='info', source={'original': 'keep'})
        self.category = InformationCategory.objects.create(title='Категория', slug='save-preview-category')
        self.add_url = reverse('admin:information_informationmaterial_add')
        self.change_url = reverse('admin:information_informationmaterial_change', args=[self.material.pk])
        self.preview_url = reverse('admin:information_informationmaterial_preview', args=[self.material.pk])
        self.data = {'title': 'После правки', 'slug': self.material.slug, 'kind': 'info',
                     'map_mode': 'categories', 'body': '<p>Новый текст</p>',
                     'categories': [self.category.pk], 'primary_category': self.category.pk,
                     '_save_preview': '1'}

    def grant(self, *codenames):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='information', codename__in=codenames))
        self.client.force_login(self.user)

    def test_change_saves_then_previews_without_publishing(self):
        self.grant('change_informationmaterial')
        self.assertContains(self.client.get(self.change_url), 'name="_save_preview"')
        response = self.client.post(self.change_url, self.data)
        self.assertRedirects(response, self.preview_url)
        self.assertContains(self.client.get(self.preview_url), 'Новый текст')
        self.material.refresh_from_db()
        self.assertEqual(self.material.title, 'После правки')
        self.assertEqual(list(self.material.categories.values_list('pk', flat=True)), [self.category.pk])
        self.assertEqual(self.material.primary_category_id, self.category.pk)
        self.assertFalse(self.material.is_active)
        self.assertEqual(self.material.source, {'original': 'keep'})
        self.assertEqual(self.client.get(self.material.get_absolute_url()).status_code, 404)

    def test_add_and_published_status(self):
        self.grant('add_informationmaterial', 'view_informationmaterial')
        self.assertContains(self.client.get(self.add_url), 'name="_save_preview"')
        data = {**self.data, 'slug': 'new-preview', 'is_active': 'on'}
        response = self.client.post(self.add_url, data)
        material = InformationMaterial.objects.get(slug='new-preview')
        self.assertRedirects(response, reverse('admin:information_informationmaterial_preview', args=[material.pk]))
        self.assertTrue(material.is_active)
        self.assertEqual(material.body, data['body'])

    def test_invalid_form_does_not_save_or_redirect(self):
        self.grant('change_informationmaterial')
        response = self.client.post(self.change_url, {**self.data, 'title': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['adminform'].form.errors)
        self.assertContains(response, 'name="_save_preview"')
        self.material.refresh_from_db()
        self.assertEqual(self.material.title, 'До правки')
        self.assertFalse(self.material.categories.exists())

    def test_view_only_cannot_save_and_add_only_has_no_preview_button(self):
        self.grant('view_informationmaterial')
        self.assertNotContains(self.client.get(self.change_url), 'name="_save_preview"')
        self.assertEqual(self.client.post(self.change_url, self.data).status_code, 403)
        self.material.refresh_from_db()
        self.assertEqual(self.material.title, 'До правки')
        self.grant('add_informationmaterial')
        self.assertNotContains(self.client.get(self.add_url), 'name="_save_preview"')
        response = self.client.post(self.add_url, {**self.data, 'slug': 'add-only'})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('/preview/', response.url)

    def test_regular_save_and_popup_are_unchanged(self):
        self.grant('change_informationmaterial')
        data = {k: v for k, v in self.data.items() if k != '_save_preview'}
        response = self.client.post(self.change_url, {**data, '_continue': '1'})
        self.assertRedirects(response, self.change_url)
        self.assertNotContains(self.client.get(self.change_url+'?_popup=1'), 'name="_save_preview"')
        response = self.client.post(self.change_url+'?_popup=1', {**self.data, '_popup': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/popup_response.html')

    def test_csrf_still_required(self):
        self.grant('change_informationmaterial')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.change_url, self.data).status_code, 403)
        self.material.refresh_from_db()
        self.assertEqual(self.material.title, 'До правки')

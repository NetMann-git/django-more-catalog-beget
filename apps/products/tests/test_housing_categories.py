"""Категории используют все привязки и сохраняют опубликованность и URL."""
from django.test import TestCase
from apps.products.models import Category, Product, ProductGalleryImage
from apps.products.category_urls import LEGACY_CATEGORY_PATHS


class HousingCategoryTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(title='Адлер', slug='adler-otdyh-s-cenami', joomla_id=73)
        self.child = Category.objects.create(title='Гостевые дома', slug='chastnyj-gostevoj-dom', parent=self.root, joomla_id=14)
        self.other = Category.objects.create(title='Другой курорт', slug='other')
        self.obj = Product.objects.create(title='Один дом', slug='one-house', category=self.child, is_active=True, price=None)
        self.obj.categories.add(self.child, self.root, self.other)

    def test_membership_primary_and_descendants_no_duplicates(self):
        response = self.client.get(self.root.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertContains(response, self.obj.title)
        self.assertContains(self.client.get(self.other.get_absolute_url()), self.obj.title)
        self.obj.categories.clear()
        self.assertEqual(self.client.get(self.root.get_absolute_url()).context['page_obj'].paginator.count, 1)

    def test_inactive_products_and_hidden_branches_not_shown(self):
        self.obj.is_active = False
        self.obj.save()
        response = self.client.get(self.root.get_absolute_url())
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertContains(response, 'пока нет опубликованных')
        self.root.is_published = False
        self.root.save()
        self.assertEqual(self.client.get(self.child.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get('/catalog/categories/'), self.root.title)

    def test_pagination_stable_no_duplicates_invalid_pages_404(self):
        for i in range(15):
            p = Product.objects.create(title=f'Дом {i:02}', slug=f'house-{i}', category=self.root, price=None)
            p.categories.add(self.root, self.child)
        first = self.client.get(self.root.get_absolute_url()).context['page_obj']
        second = self.client.get(self.root.get_absolute_url() + '?page=2').context['page_obj']
        self.assertEqual(first.paginator.count, 16)
        self.assertEqual(len(first), 12)
        self.assertEqual(len(second), 4)
        self.assertFalse({p.pk for p in first} & {p.pk for p in second})
        for page in ['invalid', '0', '-1', '999']:
            self.assertEqual(self.client.get(self.root.get_absolute_url() + '?page=' + page).status_code, 404)

    def test_catalog_alias_redirect_preserves_page_query(self):
        response = self.client.get('/catalog/category/adler-otdyh-s-cenami/?page=2')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/adler-chastnyj-sektor-tseny.html?page=2')

    def test_secondary_gallery_cover_and_sanitized_description(self):
        self.root.description = '<p>Описание</p><script>alert(1)</script>'
        self.root.save()
        ProductGalleryImage.objects.create(product=self.obj, image='jbzoo/1/images/uploads/user_1/a.jpg')
        response = self.client.get(self.root.get_absolute_url())
        self.assertContains(response, '/media/jbzoo/1/images/uploads/user_1/a.jpg')
        self.assertContains(response, '<p>Описание</p>')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_all_verified_legacy_routes_resolve_to_category(self):
        for url, slug in LEGACY_CATEGORY_PATHS.items():
            category, _ = Category.objects.get_or_create(slug=slug, defaults={'title': slug})
            response = self.client.get(url)
            if url == category.get_absolute_url():
                self.assertEqual(response.status_code, 200, url)
                self.assertEqual(response.context['category'].pk, category.pk)
            else:
                self.assertEqual(response.status_code, 301, url)
                self.assertEqual(response['Location'], category.get_absolute_url())

    def test_unknown_and_unpublished_categories_are_404(self):
        self.assertEqual(self.client.get('/catalog/category/unknown/').status_code, 404)
        self.child.is_published = False
        self.child.save()
        self.assertEqual(self.client.get(self.child.get_absolute_url()).status_code, 404)

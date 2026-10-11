"""Основная цепочка и все публичные привязки в карточке объекта."""
from django.test import TestCase
from apps.products.models import Category, Product
from apps.products.category_navigation import category_navigation


class CategoryNavigationTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(title='Курорт', slug='resort')
        self.main = Category.objects.create(title='Гостевые дома', slug='chastnyj-gostevoj-dom', parent=self.root)
        self.other = Category.objects.create(title='Другой раздел', slug='other')
        self.obj = Product.objects.create(title='Дом', slug='house', category=self.main, price=None)
        self.obj.categories.add(self.main, self.other)

    def test_primary_ancestors_and_multiple_categories(self):
        data = category_navigation(self.obj)
        self.assertEqual(data['housing_category_path'], [self.root, self.main])
        self.assertEqual({c.pk for c in data['housing_categories']}, {self.main.pk, self.other.pk})
        self.assertEqual(len(data['housing_categories']), 2)
        response = self.client.get(self.obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Объект в категориях"')
        self.assertContains(response, self.main.get_absolute_url())
        self.assertContains(response, self.other.get_absolute_url())

    def test_primary_present_without_m2m(self):
        self.obj.categories.clear()
        self.assertEqual(category_navigation(self.obj)['housing_categories'], [self.main])

    def test_hidden_parent_hides_primary_branch_but_keeps_other(self):
        self.root.is_published = False
        self.root.save()
        data = category_navigation(self.obj)
        self.assertEqual(data['housing_category_path'], [])
        self.assertEqual(data['housing_categories'], [self.other])
        response = self.client.get(self.obj.get_absolute_url())
        self.assertNotContains(response, 'href="' + self.main.get_absolute_url() + '"')

    def test_no_categories_links_to_index_without_empty_group(self):
        self.obj.category = None
        self.obj.save()
        self.obj.categories.clear()
        response = self.client.get(self.obj.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/catalog/categories/')
        self.assertNotContains(response, 'aria-label="Объект в категориях"')

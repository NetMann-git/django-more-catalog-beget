"""Дерево админки: порядок, поиск, права и сохранение штатных действий."""
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from apps.products.category_tree_admin import arrange_categories, category_tree_title
from apps.products.models import Category


class TreeOrderingTests(SimpleTestCase):
    def test_depth_first_sibling_order_and_orphans(self):
        objs = [Category(pk=1, title='Корень', slug='root', sort_order=2),
                Category(pk=2, title='Ребёнок', parent_id=1, sort_order=1),
                Category(pk=3, title='Внук', parent_id=2),
                Category(pk=4, title='Другой корень', sort_order=1),
                Category(pk=5, title='Второй ребёнок', parent_id=1, sort_order=2)]
        rows = arrange_categories(reversed(objs))
        self.assertEqual([o.pk for o in rows], [4, 1, 2, 3, 5])
        self.assertEqual([o.tree_depth for o in rows], [0, 0, 1, 2, 1])
        self.assertEqual(rows[3].tree_ancestors, (1, 2))
        orphan = arrange_categories([objs[2]])[0]
        self.assertEqual(orphan.tree_depth, 0)

    def test_corrupt_cycle_keeps_all_nodes_once(self):
        rows = arrange_categories([Category(pk=1, parent_id=2), Category(pk=2, parent_id=1)])
        self.assertEqual({o.pk for o in rows}, {1, 2})
        self.assertEqual(len(rows), 2)

    def test_titles_are_escaped(self):
        obj = Category(pk=1, title='<script>alert(1)</script>')
        arrange_categories([obj])
        rendered = str(category_tree_title(obj))
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)


class CategoryTreeAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='tree-admin', password='test-password')
        self.client.force_login(self.user)
        self.root = Category.objects.create(title='Корень', slug='root', sort_order=2)
        self.child = Category.objects.create(title='Дочерняя', slug='child', parent=self.root, sort_order=1)
        self.grandchild = Category.objects.create(title='Внук', slug='grandchild', parent=self.child)
        self.other = Category.objects.create(title='Другой корень', slug='other', sort_order=1, is_published=False)
        self.url = reverse('admin:products_category_changelist')

    def test_tree_and_admin_controls(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        rows = response.context['cl'].result_list
        self.assertEqual([o.pk for o in rows], [self.other.pk, self.root.pk, self.child.pk, self.grandchild.pk])
        self.assertContains(response, 'Развернуть всё')
        self.assertContains(response, 'category-tree.js')
        self.assertContains(response, reverse('admin:products_category_change', args=[self.child.pk]))
        self.assertContains(response, 'name="action"')
        self.assertContains(response, 'name="_selected_action"', count=4)

    def test_search_filter_and_autocomplete_remain_available(self):
        response = self.client.get(self.url, {'q': 'Внук'})
        self.assertEqual([o.pk for o in response.context['cl'].result_list], [self.grandchild.pk])
        response = self.client.get(self.url, {'is_published__exact': '0'})
        self.assertEqual([o.pk for o in response.context['cl'].result_list], [self.other.pk])
        response = self.client.get(reverse('admin:autocomplete'), {
            'app_label': 'products', 'model_name': 'category', 'field_name': 'parent', 'term': 'root'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['id'] for r in response.json()['results']], [str(self.root.pk)])

    def test_no_branch_split_by_page(self):
        Category.objects.bulk_create([Category(title=f'Дочерняя {i}', slug=f'child-{i}', parent=self.root) for i in range(105)])
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['cl'].result_list), 109)
        self.assertFalse(response.context['cl'].multi_page)

    def test_nonstaff_cannot_view_tree(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

"""Множественные категории: формы, фильтрация, счётчик и перенос старых связей."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from apps.products.models import Product, Category
from apps.products.forms import ProductForm
from apps.products.multiple_attribute_forms import MultipleProductAdminForm
from apps.products.filters import CatalogFilter


class ProductCategoriesTests(TestCase):
    def setUp(self):
        self.main = Category.objects.create(title='Адлер', slug='adler')
        self.second = Category.objects.create(title='Все варианты', slug='all')
        self.empty = Category.objects.create(title='Пустая', slug='empty')
        self.product = Product.objects.create(title='Дом', slug='house', category=self.main, price=None)
        self.data = {'title':'Дом', 'slug':'house', 'currency':'RUB', 'availability_status':'in_stock', 'category':str(self.main.pk), 'categories':[str(self.second.pk)], 'is_active':'on', 'rating':'0', 'reviews_count':'0'}
        # Использовать действующее значение по умолчанию проекта.
        self.data['availability_status'] = self.product.availability_status

    def test_both_forms_save_main_and_multiple_categories(self):
        for form_class in (ProductForm, MultipleProductAdminForm):
            with self.subTest(form=form_class):
                form = form_class(self.data, instance=self.product)
                self.assertTrue(form.is_valid(), form.errors)
                product = form.save()
                self.assertEqual(set(product.categories.values_list('pk', flat=True)), {self.main.pk, self.second.pk})
                self.assertEqual(product.category_id, self.main.pk)
                self.assertEqual(product.slug, 'house')

    def test_main_required_if_categories_selected(self):
        data = {**self.data, 'category':''}
        for form_class in (ProductForm, MultipleProductAdminForm):
            form = form_class(data, instance=self.product)
            self.assertFalse(form.is_valid())
            self.assertIn('category', form.errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.category_id, self.main.pk)

    def test_remove_additional_and_change_main(self):
        self.product.categories.set([self.main,self.second])
        form = ProductForm({**self.data,'category':str(self.second.pk),'categories':[]}, instance=self.product)
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        self.assertEqual(set(self.product.categories.values_list('pk', flat=True)),{self.second.pk})
        self.assertEqual(self.product.category_id,self.second.pk)
        self.assertEqual(self.product.slug,'house')

    def test_invalid_category_id_does_not_save(self):
        form = ProductForm({**self.data,'categories':['999999']},instance=self.product)
        self.assertFalse(form.is_valid())
        self.assertIn('categories',form.errors)
        self.assertFalse(self.product.categories.exists())

    def test_filter_includes_primary_fallback_and_memberships_once(self):
        self.product.categories.set([self.main,self.second])
        legacy = Product.objects.create(title='Старое жильё',slug='old',category=self.main,price=None)
        for category, expected in ((self.main,{self.product.pk,legacy.pk}),(self.second,{self.product.pk}),(self.empty,set())):
            rows = list(CatalogFilter({'category':str(category.pk)}).apply(Product.objects.all()))
            self.assertEqual(len(rows),len(expected))
            self.assertEqual({r.pk for r in rows},expected)
        self.assertFalse(CatalogFilter({'category':'invalid'}).apply(Product.objects.all()).exists())

    def test_counter_counts_union_once_in_one_query(self):
        self.product.categories.set([self.main,self.second])
        Product.objects.create(title='Скрытый',slug='hidden',category=self.main,is_active=False,price=None)
        with CaptureQueriesContext(connection) as queries:
            rows = list(admin.site._registry[Category].get_queryset(RequestFactory().get('/')))
            counts = {r.pk:r.elements_count for r in rows}
        self.assertEqual(len(queries),1)
        self.assertEqual(counts,{self.main.pk:2,self.second.pk:1,self.empty.pk:0})

    def test_membership_changes_clear_cache_after_commit(self):
        for operation in (lambda:self.product.categories.add(self.second), lambda:self.product.categories.remove(self.second),lambda:self.product.categories.clear()):
            cache.set('catalog_queryset','cached')
            with self.captureOnCommitCallbacks(execute=True):
                operation()
            self.assertIsNone(cache.get('catalog_queryset'))

    def test_admin_and_manager_fields_present(self):
        user=get_user_model().objects.create_superuser('multi-cat-admin',password='test')
        self.client.force_login(user)
        response=self.client.get(reverse('admin:products_product_change',args=[self.product.pk]))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Родительская категория (основная)')
        self.assertContains(response,'name="categories"')
        self.assertEqual(ProductForm(instance=self.product).fields['categories'].widget.__class__.__name__,'CheckboxSelectMultiple')


class CategoryMembershipMigrationTests(TransactionTestCase):
    def test_existing_main_becomes_membership_without_changing_slug(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes()
        before=[('products','0013_alter_category_options_category_description_and_more')]
        after=[('products','0014_product_categories_alter_product_category')]
        try:
            executor.migrate(before)
            apps=executor.loader.project_state(before).apps
            category=apps.get_model('products','Category').objects.create(title='Адлер',slug='adler')
            old=apps.get_model('products','Product').objects.create(title='Дом',slug='legacy-house',category_id=category.pk,price=None)
            unassigned=apps.get_model('products','Product').objects.create(title='Без категории',slug='unassigned',price=None)
            executor=MigrationExecutor(connection);executor.migrate(after)
            model=executor.loader.project_state(after).apps.get_model('products','Product')
            product=model.objects.get(pk=old.pk)
            self.assertEqual(product.category_id,category.pk)
            self.assertEqual(product.slug,'legacy-house')
            self.assertEqual(list(product.categories.values_list('pk',flat=True)),[category.pk])
            self.assertFalse(model.objects.get(pk=unassigned.pk).categories.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)

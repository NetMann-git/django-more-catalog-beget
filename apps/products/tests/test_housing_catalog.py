"""Комбинированный подбор жилья не раскрывает скрытые записи и сохраняет фильтры."""
from django.test import TestCase
from apps.products.models import Category, Brand, Product


class HousingCatalogTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(title='Адлер', slug='adler')
        self.child = Category.objects.create(title='У моря', slug='sea', parent=self.root)
        self.other = Category.objects.create(title='Сочи', slug='sochi')
        self.brand = Brand.objects.create(name='Гостевой дом', slug='guest-house')
        self.obj = Product.objects.create(title='Орион', slug='orion', category=self.child, brand=self.brand, address='Морская, 2', price=None)
        self.obj.categories.add(self.child, self.root)
        self.unknown = Product.objects.create(title='Квартира', slug='flat', category=self.other, brand=None, price=None)

    def get(self, **params):
        return self.client.get('/catalog/housing/', params)

    def test_all_and_combined_category_type_query_filters(self):
        self.assertEqual(self.get().context['page_obj'].paginator.count, 2)
        response = self.get(category='adler', housing_type='guest-house', q='Морская')
        self.assertEqual(list(response.context['page_obj']), [self.obj])
        self.assertEqual(len(response.context['cards']), 1)
        self.assertEqual(self.get(category='sochi', housing_type='guest-house').context['page_obj'].paginator.count, 0)
        self.assertContains(self.get(q='орион'), self.obj.title)

    def test_primary_without_m2m_and_untyped(self):
        self.obj.categories.clear()
        self.assertEqual(list(self.get(category='adler').context['page_obj']), [self.obj])
        self.assertEqual(list(self.get(housing_type='untyped').context['page_obj']), [self.unknown])

    def test_invalid_hidden_choices_show_error_and_no_results(self):
        self.root.is_published = False
        self.root.save()
        for params in [{'category': 'adler'}, {'category': 'sea'}, {'housing_type': 'missing'}, {'q': 'a' * 121}]:
            response = self.get(**params)
            self.assertTrue(response.context['filter_form'].errors)
            self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_inactive_products_and_types_are_not_visible(self):
        self.obj.is_active = False
        self.obj.save()
        response = self.get()
        self.assertEqual(list(response.context['page_obj']), [self.unknown])
        self.assertNotContains(response, 'value="guest-house"')

    def test_pagination_preserves_conditions_and_no_duplicates(self):
        for i in range(13):
            obj = Product.objects.create(title=f'Морской {i}', slug=f'house-{i}', category=self.child, brand=self.brand, price=None)
            obj.categories.add(self.root, self.child)
        params = {'category': 'adler', 'housing_type': 'guest-house', 'q': 'Морской'}
        first = self.get(**params)
        second = self.get(**params, page=2)
        self.assertEqual(first.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(second.context['page_obj']), 1)
        self.assertContains(first, 'category=adler&amp;housing_type=guest-house&amp;q=')
        self.assertFalse({p.pk for p in first.context['page_obj']} & {p.pk for p in second.context['page_obj']})
        self.assertEqual(self.get(page=999).status_code, 404)

    def test_navigation_links_and_query_escape(self):
        response = self.get(q='<script>alert(1)</script>')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '/catalog/housing/')
        self.assertContains(self.client.get('/catalog/categories/'), 'Подобрать жильё по параметрам')

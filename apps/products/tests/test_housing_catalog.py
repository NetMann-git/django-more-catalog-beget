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

    def test_price_and_amenities_apply_to_list_and_entire_map(self):
        from apps.products.models import AttributeType, AttributeValue, ProductAttribute

        kind = AttributeType.objects.create(name='Удобства', slug='amenities', allow_multiple=True)
        wifi = AttributeValue.objects.create(attribute_type=kind, value='Wi-Fi')
        parking = AttributeValue.objects.create(attribute_type=kind, value='Парковка')
        self.obj.price = 3000
        self.obj.map_coordinates = '39.9,43.4'
        self.obj.image = 'housing/orion.webp'
        self.obj.save()
        self.unknown.price = 3000
        self.unknown.map_coordinates = '39.8,43.5'
        self.unknown.save()
        for product, value in [(self.obj, wifi), (self.obj, parking), (self.unknown, wifi)]:
            ProductAttribute.objects.create(product=product, attribute_type=kind, attribute_value=value)
        params = {'price_min': '2000', 'price_max': '4000', 'amenities': [wifi.pk, parking.pk]}
        listing = self.get(**params)
        self.assertEqual(list(listing.context['page_obj']), [self.obj])
        self.assertContains(listing, 'Снять фильтр: Wi-Fi')
        self.assertIn(f'amenities={parking.pk}', listing.context['map_query'])
        mapped = self.get(**params, view='map', page=2)
        self.assertEqual(mapped.context['result_count'], 1)
        self.assertEqual([point['id'] for point in mapped.context['map_data']['points']], [self.obj.pk])
        self.assertEqual(mapped.context['map_data']['points'][0]['photo'], self.obj.image.url)
        self.assertIn(f'amenities={wifi.pk}', mapped.context['pagination_query'])
        self.assertTrue(self.get(price_min=4000, price_max=2000).context['filter_form'].errors)

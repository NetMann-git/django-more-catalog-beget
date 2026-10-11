from django.test import TestCase
from apps.products.models import Product, AttributeType, AttributeValue, ProductAttribute
from apps.products.comparison_service import ComparisonService


class ComparisonMultipleValuesTests(TestCase):
    def setUp(self):
        self.first = Product.objects.create(title='Первый дом', slug='first', price=None)
        self.second = Product.objects.create(title='Второй дом', slug='second', price=None)
        self.kind = AttributeType.objects.create(name='Удобства', slug='amenities-test', data_type='choice', allow_multiple=True)
        self.wifi = AttributeValue.objects.create(attribute_type=self.kind, value='Wi-Fi', sort_order=1)
        self.pool = AttributeValue.objects.create(attribute_type=self.kind, value='Бассейн', sort_order=2)
        ProductAttribute.objects.create(product=self.first, attribute_type=self.kind, attribute_value=self.pool, sort_order=2)
        ProductAttribute.objects.create(product=self.first, attribute_type=self.kind, attribute_value=self.wifi, sort_order=1)

    def test_multiple_values_keep_order_and_missing_dash(self):
        rows = ComparisonService.get_attributes_rows([self.first, self.second])
        self.assertEqual(rows, [{'name': 'Удобства', self.first.pk: 'Wi-Fi; Бассейн', self.second.pk: '—'}])
        self.assertEqual(ProductAttribute.objects.filter(product=self.first).count(), 2)

    def test_blank_value_does_not_replace_selected_values(self):
        ProductAttribute.objects.create(product=self.first, attribute_type=self.kind, attribute_value=None, sort_order=3)
        blank = AttributeValue.objects.create(attribute_type=self.kind, value='   ')
        ProductAttribute.objects.create(product=self.second, attribute_type=self.kind, attribute_value=blank)
        rows = ComparisonService.get_attributes_rows([self.first, self.second])
        self.assertEqual(rows[0][self.first.pk], 'Wi-Fi; Бассейн')
        self.assertEqual(rows[0][self.second.pk], '—')
        with self.assertNumQueries(1):
            ComparisonService.get_attributes_rows([self.first, self.second])

    def test_table_renders_all_values_as_escaped_text(self):
        dangerous = AttributeValue.objects.create(attribute_type=self.kind, value='<script>bad()</script>')
        ProductAttribute.objects.create(product=self.first, attribute_type=self.kind, attribute_value=dangerous)
        session = self.client.session
        session['comparison'] = [self.first.pk, self.second.pk]
        session.save()
        response = self.client.get('/catalog/comparison/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wi-Fi')
        self.assertContains(response, 'Бассейн')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')

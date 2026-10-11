from django.test import TestCase
from apps.products.models import Brand, Product, ProductGalleryImage


class HousingTypePageTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name='Гостевые дома', slug='guest-houses', description='<p>Описание <strong>жилья</strong></p><script>alert(1)</script>')

    def test_original_cards_and_visibility(self):
        product = Product.objects.create(title='Дом Орион', slug='orion', brand=self.brand, joomla_id=9501, price=None)
        ProductGalleryImage.objects.create(product=product, image='housing/original.jpg')
        Product.objects.create(title='Скрытый дом', slug='hidden', brand=self.brand, price=None, is_active=False)
        Product.objects.create(title='Чужой тип', slug='other', price=None)
        response = self.client.get(self.brand.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        for value in [product.get_absolute_url(), '/media/housing/original.jpg', 'housing-public-page', '<strong>жилья</strong>', '?housing_type=guest-houses']:
            self.assertContains(response, value)
        for value in ['Скрытый дом', 'Чужой тип', '<script>alert(1)</script>', 'В наличии', 'Под заказ']:
            self.assertNotContains(response, value)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_pagination_and_invalid_pages(self):
        for number in range(13):
            Product.objects.create(title=f'Дом {number:02}', slug=f'house-{number}', brand=self.brand, price=None)
        response = self.client.get(self.brand.get_absolute_url())
        self.assertEqual(len(response.context['cards']), 12)
        response = self.client.get(self.brand.get_absolute_url(), {'page': 2})
        self.assertEqual(response.context['cards'][0]['product'].title, 'Дом 12')
        self.assertContains(response, self.brand.get_absolute_url()+'?page=2')
        for page in [0, -1, 3, 'bad']:
            self.assertEqual(self.client.get(self.brand.get_absolute_url(), {'page': page}).status_code, 404)

    def test_empty_type_and_missing_type(self):
        self.assertContains(self.client.get(self.brand.get_absolute_url()), 'Жильё этого типа пока не опубликовано.')
        self.assertEqual(self.client.get('/catalog/brand/missing-type/').status_code, 404)

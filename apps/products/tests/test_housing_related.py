from django.test import TestCase
from apps.products.models import Product, Category, Brand, ProductGalleryImage
from apps.products.housing_related import related_housing


class HousingRelatedTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(title='Курорт', slug='resort')
        self.brand = Brand.objects.create(name='Гостевые дома', slug='guest')
        self.current = Product.objects.create(title='Текущий', slug='current', price=None, category=self.category, brand=self.brand)

    def product(self, title, **kwargs):
        return Product.objects.create(title=title, slug=title, price=None, **kwargs)

    def test_priority_multiple_categories_and_hidden(self):
        common = self.product('z-common', brand=self.brand)
        common.categories.add(self.category)
        category_only = self.product('a-category', category=self.category)
        type_only = self.product('b-type', brand=self.brand)
        self.product('hidden', category=self.category, brand=self.brand, is_active=False)
        self.product('unrelated')
        self.assertEqual([p.pk for p in related_housing(self.current)], [common.pk, category_only.pk, type_only.pk])
        self.assertEqual(len(related_housing(self.current, limit=1)), 1)

    def test_hidden_ancestor_and_no_arbitrary_fallback(self):
        hidden = Category.objects.create(title='Скрытая', slug='hidden', is_published=False)
        child = Category.objects.create(title='Дочерняя', slug='child', parent=hidden)
        self.current.brand = None
        self.current.category = child
        self.current.save()
        self.product('same-hidden', category=child)
        self.assertEqual(related_housing(self.current), [])

    def test_detail_blocks_original_photo_and_history_order(self):
        first = self.product('first', brand=self.brand, joomla_id=9601)
        last = self.product('last', category=self.category, joomla_id=9602)
        ProductGalleryImage.objects.create(product=first, image='housing/original.jpg')
        session = self.client.session
        session['recently_viewed'] = [last.pk, first.pk]
        session.save()
        response = self.client.get(self.current.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c['product'].pk for c in response.context['housing_recent_cards']], [last.pk, first.pk])
        self.assertContains(response, '/media/housing/original.jpg')
        self.assertContains(response, first.get_absolute_url())
        self.assertContains(response, f'/wishlist/toggle/{first.pk}/')
        self.assertContains(response, f'/catalog/comparison/toggle/{first.pk}/')
        self.assertContains(response, 'Вернуться к подбору жилья')
        self.assertNotContains(response, 'В наличии')
        self.assertNotContains(response, 'Под заказ')

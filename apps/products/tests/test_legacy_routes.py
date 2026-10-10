"""Новый путь Joomla открывает только объект с соответствующим исходным URL."""
from django.test import TestCase
from apps.products.models import Product
from apps.products.legacy_urls import LEGACY_PREFIXES


class LegacyRouteTests(TestCase):
    def test_all_prefixes_render_only_matching_published_object(self):
        obj = Product.objects.create(title='Дом', slug='legacy-house', joomla_id=99999, is_active=True)
        for prefix in LEGACY_PREFIXES:
            with self.subTest(prefix=prefix):
                url = f'/{prefix}/{obj.slug}.html'
                obj.joomla_url = 'https://xn----7sblqcj4aok5d9b.xn--p1ai' + url
                obj.save()
                self.assertEqual(obj.get_absolute_url(), url)
                self.assertEqual(self.client.get(url).status_code, 200)
                other = next(p for p in LEGACY_PREFIXES if p != prefix)
                self.assertEqual(self.client.get(f'/{other}/{obj.slug}.html').status_code, 404)
                moved = self.client.get(f'/catalog/{obj.slug}/')
                self.assertEqual(moved.status_code, 301)
                self.assertEqual(moved['Location'], url)
        obj.is_active = False
        obj.save()
        self.assertEqual(self.client.get(obj.get_absolute_url()).status_code, 404)

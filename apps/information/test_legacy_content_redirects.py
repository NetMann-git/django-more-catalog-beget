from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.http import Http404
from .content_links import MAPS_ALIAS, REVIEWS_ALIAS, REVIEW_PATH, normalize_content_link
from .link_audit import check_target
from .models import InformationMaterial
from .views import legacy_content_redirect


class LegacyContentRedirectTests(TestCase):
    def setUp(self):
        self.review = InformationMaterial.objects.create(joomla_id=131, slug='reviews-legacy', title='Отзывы об отдыхе', kind='info', is_active=True, body='Отзывы отдыхающих', source={'archive': 'unchanged'})

    def test_aliases_return_single_permanent_redirect_to_public_pages(self):
        for source, destination in [(MAPS_ALIAS, reverse('information:maps')), (REVIEWS_ALIAS, REVIEW_PATH)]:
            with self.subTest(source=source):
                response = self.client.get(source)
                self.assertRedirects(response, destination, status_code=301)
                final = self.client.get(source, follow=True)
                self.assertEqual(final.redirect_chain, [(destination, 301)])
                self.assertEqual(final.status_code, 200)
                self.assertContains(final, 'rel="canonical"')
                self.assertEqual(normalize_content_link(source), destination)
                self.assertEqual(self.client.head(source).status_code, 301)

    def test_query_parameters_remain_local_and_are_preserved(self):
        query = 'utm_source=joomla&tag=a&tag=b&next=https%3A%2F%2Fevil.example%2F'
        for source, destination in [(MAPS_ALIAS, reverse('information:maps')), (REVIEWS_ALIAS, REVIEW_PATH)]:
            response = self.client.get(source+'?'+query)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response.url, destination+'?'+query)
            self.assertTrue(response.url.startswith('/'))

    def test_missing_or_hidden_review_stays_404_and_data_unchanged(self):
        before = list(InformationMaterial.objects.values())
        self.client.get(REVIEWS_ALIAS)
        self.assertEqual(list(InformationMaterial.objects.values()), before)
        self.review.is_active = False
        self.review.save()
        self.assertEqual(self.client.get(REVIEWS_ALIAS).status_code, 404)
        self.review.delete()
        self.assertEqual(self.client.get(REVIEWS_ALIAS).status_code, 404)
        self.assertEqual(self.client.get(MAPS_ALIAS).status_code, 301)

    def test_post_and_unknown_alias_are_rejected(self):
        for alias in [MAPS_ALIAS, REVIEWS_ALIAS]:
            response = self.client.post(alias, {'next': '//evil.example'})
            self.assertEqual(response.status_code, 405)
        with self.assertRaises(Http404):
            legacy_content_redirect(RequestFactory().get('/unknown-alias.html?next=https://evil.example/'))

    @override_settings(ALLOWED_HOSTS=['audit.local'])
    def test_audit_can_follow_alias_and_sitemap_uses_canonical_only(self):
        from django.test import Client
        client = Client(HTTP_HOST='audit.local')
        for alias in [MAPS_ALIAS, REVIEWS_ALIAS]:
            result = check_target(client, alias)
            self.assertEqual(result['status'], 200)
            self.assertEqual(len(result['redirects']), 1)
            self.assertNotIn('problem', result)
            self.assertNotIn('skipped', result)
        response = client.get('/sitemap.xml', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'https://audit.local'+MAPS_ALIAS+'<')
        self.assertNotContains(response, 'https://audit.local'+REVIEWS_ALIAS+'<')
        self.assertContains(response, 'https://audit.local'+REVIEW_PATH+'<')

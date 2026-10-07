"""HTML тарифов: совместимость Joomla, защита и сохранение исходника."""
from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from apps.products.admin import ProductAdmin
from apps.products.forms import ProductForm
from apps.products.models import Product
from apps.products.price_widgets import PricesWidget
from apps.products.prices_html import sanitize_prices
from apps.users.constants import ROLE_MANAGER

EXAMPLE = '''<h2>Цены</h2><p><span style="color:#ff0000;font-size:14pt"><strong>За сутки</strong></span></p>
<div class="table-responsive"><table class="table table-striped table-bordered"><tbody><tr><td colspan="2">май</td><td>июнь</td></tr><tr><td>500 - 700</td><td>1000</td><td>1500</td></tr></tbody></table></div>
<p>{source}<span style="font-family:courier new">&lt;div style="position:relative;overflow:hidden;"&gt;&lt;iframe src="https://yandex.ru/map-widget/v1/-/CCUFIJHLHB" width="560" height="400" allowfullscreen="true"&gt;&lt;/iframe&gt;&lt;/div&gt;</span>{/source}</p>
<video style="display:block;margin-left:auto;margin-right:auto" src="images/uploads/user_606/video-2022-04-13-2.mp4" controls width="300" height="400"></video>
<video src="images/uploads/user_606/video-2022-04-13-3.mp4" controls></video>'''


class PricesSanitizerTests(SimpleTestCase):
    def test_tables_format_video_and_joomla_panorama(self):
        rendered = sanitize_prices(EXAMPLE)
        soup = BeautifulSoup(rendered, 'html.parser')
        self.assertEqual(len(soup.find_all('video')), 2)
        self.assertEqual(soup.video['src'], '/images/uploads/user_606/video-2022-04-13-2.mp4')
        self.assertEqual(soup.iframe['src'], 'https://yandex.ru/map-widget/v1/-/CCUFIJHLHB')
        self.assertEqual(soup.td['colspan'], '2')
        self.assertIn('color:#ff0000;font-size:14pt', rendered)
        self.assertNotIn('{source}', rendered)
        self.assertNotIn('&lt;iframe', rendered)
        self.assertIn('allowfullscreen', rendered)

    def test_scripts_handlers_css_and_forms_are_removed(self):
        result = sanitize_prices('''<script>alert(1)</script><img src="/media/x.png" onerror="alert(2)"><p style="color:red;position:fixed;background:url(javascript:alert(1));font-size:14pt" onclick="x()">Текст</p><svg><script>x()</script></svg><form><input name="csrfmiddlewaretoken"></form><iframe srcdoc="bad" src="https://evil.test"></iframe>''')
        self.assertNotIn('alert', result)
        self.assertNotIn('onerror', result)
        self.assertNotIn('onclick', result)
        self.assertNotIn('url(', result)
        self.assertNotIn('fixed', result)
        self.assertNotIn('iframe', result)
        self.assertIn('color:red;font-size:14pt', result)

    def test_frame_exact_host_and_path_required(self):
        bad = ['https://yandex.ru.evil.test/map-widget/x', 'https://yandex.ru/other', '//yandex.ru/map-widget/x', 'http://yandex.ru/map-widget/x', 'https://yandex.ru@evil.test/map-widget/x', 'https://yandex.ru:444/map-widget/x', '/media/a.html', 'javascript:alert(1)', 'data:text/html,x']
        for url in bad:
            with self.subTest(url=url):
                self.assertNotIn('<iframe', sanitize_prices(f'<iframe src="{url}"></iframe>'))
        for url in ['https://www.youtube.com/embed/x', 'https://www.youtube-nocookie.com/embed/x', 'https://rutube.ru/play/embed/x', 'https://player.vimeo.com/video/1']:
            self.assertIn('<iframe', sanitize_prices(f'<iframe src="{url}"></iframe>'))

    def test_malformed_html_does_not_reintroduce_active_content(self):
        attacks = ['<math><mtext><table><mglyph><style><!--</style><img title="--><img src=x onerror=alert(1)>">', '<img src="jav&#x61;script:alert(1)">', '<a href="java\nscript:alert(1)">x</a>', '<iframe src="https://yandex.ru/map-widget/x" onload="x()" srcdoc="<script>x()</script>"></iframe>', '<!--<script>hidden</script>--><b>ok</b>']
        for value in attacks:
            soup = BeautifulSoup(sanitize_prices(value), 'html.parser')
            self.assertFalse(soup.find_all(['script', 'style', 'svg', 'math']))
            for node in soup.find_all(True):
                self.assertFalse(any(key.startswith('on') or key == 'srcdoc' for key in node.attrs))

    def test_plain_text_and_font_format_survive(self):
        self.assertEqual(sanitize_prices('Цена 500 & 700'), 'Цена 500 &amp; 700')
        self.assertIn('font-size:24px', sanitize_prices('<font color="#ff0000" size="5">Цена</font>'))
        self.assertEqual(sanitize_prices(''), '')
        self.assertEqual(sanitize_prices(sanitize_prices(EXAMPLE)), sanitize_prices(EXAMPLE))


class PricesEditorTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('prices-manager', password='test')
        user.profile.role = ROLE_MANAGER
        user.profile.save()
        self.client.force_login(user)
        self.product = Product.objects.create(title='Дом', slug='prices-house', price_description=EXAMPLE, is_active=True)
        self.url = reverse('catalog:product_edit', args=[self.product.pk])

    def test_both_forms_use_editor_and_archive_is_not_editable(self):
        self.assertIsInstance(ProductForm().fields['price_description'].widget, PricesWidget)
        staff = get_user_model().objects.create_superuser('prices-admin', 'test@example.test', 'test')
        from django.test import RequestFactory
        request = RequestFactory().get('/admin/products/product/')
        request.user = staff
        form = ProductAdmin(Product, admin.site).get_form(request, self.product)()
        self.assertIsInstance(form.fields['price_description'].widget, PricesWidget)
        self.assertNotIn('price_description_source', form.fields)
        self.assertNotIn('price_description_source', ProductForm().fields)
        response = self.client.get(self.url)
        self.assertContains(response, 'products/js/prices-editor.js')
        self.assertContains(response, 'data-prices-editor="true"')
        self.assertContains(response, '&lt;h2&gt;Цены&lt;/h2&gt;')

    def test_edit_clear_and_invalid_form_preserve_archive(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.price_description_source, EXAMPLE)
        data = {'title':'Дом','slug':'prices-house','currency':'RUB','availability_status':'in_stock','is_active':'on','price_description':'<table><tr><td>Июль 2026</td></tr></table>'}
        self.assertEqual(self.client.post(self.url, data).status_code,302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price_description, data['price_description'])
        self.assertEqual(self.product.price_description_source, EXAMPLE)
        data['price_description'] = '<p>Новый текст</p>'
        data['contact_email'] = 'wrong'
        self.assertEqual(self.client.post(self.url, data).status_code,200)
        self.product.refresh_from_db()
        self.assertNotEqual(self.product.price_description, data['price_description'])
        data['contact_email'] = ''
        data['price_description'] = ''
        self.assertEqual(self.client.post(self.url, data).status_code,302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price_description,'')
        self.assertEqual(self.product.price_description_source,EXAMPLE)

    def test_public_render_sanitizes_but_database_keeps_exact_html(self):
        attack = '<script>UNSAFE_MARKER()</script><p onclick="attack()">Цена 700</p>'
        self.product.price_description = EXAMPLE + attack
        self.product.save()
        response = self.client.get(reverse('catalog:product_detail', args=[self.product.slug]))
        self.assertContains(response, 'https://yandex.ru/map-widget/v1/-/CCUFIJHLHB')
        self.assertContains(response, '/images/uploads/user_606/video-2022-04-13-2.mp4')
        self.assertNotContains(response,'UNSAFE_MARKER')
        self.assertNotContains(response,'onclick="attack()"')
        self.product.refresh_from_db()
        self.assertEqual(self.product.price_description,EXAMPLE+attack)
        self.assertEqual(self.product.price_description_source,EXAMPLE)

    def test_partial_save_does_not_archive_unsaved_html(self):
        product = Product.objects.create(title='Другой дом', slug='another-prices')
        product.price_description = '<p>Не сохранено</p>'
        product.title = 'Переименован'
        product.save(update_fields=['title'])
        product.refresh_from_db()
        self.assertEqual(product.price_description_source,'')
        product.price_description = EXAMPLE
        product.save(update_fields=['price_description'])
        product.refresh_from_db()
        self.assertEqual(product.price_description_source, EXAMPLE)


class PricesMigrationTests(TransactionTestCase):
    def test_migration_archives_existing_html_without_changing_price(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('products','0011_product_additional_services_and_more')])
            Old = executor.loader.project_state([('products','0011_product_additional_services_and_more')]).apps.get_model('products','Product')
            old = Old.objects.create(title='Прежний дом',slug='old-prices',price=None,price_description=EXAMPLE)
            executor = MigrationExecutor(connection)
            executor.migrate([('products','0012_product_prices_html_source')])
            New = executor.loader.project_state([('products','0012_product_prices_html_source')]).apps.get_model('products','Product')
            obj = New.objects.get(pk=old.pk)
            self.assertEqual(obj.price_description,EXAMPLE)
            self.assertEqual(obj.price_description_source,EXAMPLE)
            self.assertIsNone(obj.price)
        finally:
            MigrationExecutor(connection).migrate(latest)


class TinyMCECompatibilityTests(SimpleTestCase):
    def test_editor_widget_uses_local_tinymce(self):
        widget = PricesWidget()
        self.assertIn('products/vendor/tinymce/tinymce.min.js', widget.media._js)
        rendered = widget.render('price_description', EXAMPLE, attrs={'id':'id_price_description'})
        self.assertIn('data-prices-editor="true"', rendered)
        self.assertIn('&lt;table', rendered)

    def test_legacy_table_styles_and_attributes_survive_preview(self):
        source = '<table border="1" cellspacing="2" cellpadding="4" width="100%" class="old-prices"><tr><td rowspan="2" valign="middle" style="border-top-color:#ff0000;padding-left:12px;vertical-align:middle;line-height:1.5">Цена</td></tr></table>'
        result = sanitize_prices(source, for_editor=True)
        self.assertIn('width="100%"', result)
        self.assertIn('cellpadding="4"',result)
        self.assertIn('old-prices',result)
        self.assertIn('border-top-color:#ff0000',result)
        self.assertIn('padding-left:12px',result)
        self.assertIn('line-height:1.5',result)

    def test_editor_preview_does_not_allow_active_content(self):
        result = sanitize_prices('<div class="old-prices" style="position:absolute;left:0px;background:url(javascript:bad)"><script>attack()</script><iframe src="https://evil.test" onload="attack()"></iframe></div>', for_editor=True)
        self.assertNotIn('attack',result)
        self.assertNotIn('iframe',result)
        self.assertNotIn('url(',result)

    def test_legacy_headings_superscript_and_direction_survive(self):
        result = sanitize_prices('<h1>Цены</h1><p dir="ltr">м<sup>2</sup></p>',for_editor=True)
        self.assertIn('<h1>Цены</h1>',result)
        self.assertIn('<sup>2</sup>',result)
        self.assertIn('dir="ltr"',result)

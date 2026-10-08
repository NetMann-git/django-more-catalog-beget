"""Метка и центр независимы; исходная точность и старые записи сохраняются."""
from copy import deepcopy
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from apps.products.map_data import coordinate_pair, product_map, apply_map_import
from apps.products.map_widgets import MapCoordinatesWidget
from apps.products.models import Product
from apps.products.forms import ProductForm
from apps.products.multiple_attribute_forms import MultipleProductAdminForm

MARKER = '38.887676244734415, 44.19781059487658'
CENTER = '38.887205,44.196131'


class CoordinateTests(SimpleTestCase):
    def test_preserves_precision_and_longlat_order(self):
        self.assertEqual(coordinate_pair(MARKER),['38.887676244734415','44.19781059487658'])
        self.assertEqual(coordinate_pair('0, 0'),['0','0'])
        self.assertIsNone(coordinate_pair(''))

    def test_rejects_bad_format_nonfinite_and_range(self):
        for value in ('NaN,0','0,Infinity','181,0','0,91','0,0,0','alert(1),0',',0','x,y'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                coordinate_pair(value)

    def test_source_import_preserves_all_original_values(self):
        source={'location':MARKER,'mapcenter':CENTER,'zoom':'15','ballun':'<p>Описание</p>','file':'images/marker.png','onlycurrentitem':'1'}
        obj=Product(title='Дом',slug='house')
        apply_map_import(obj,source)
        self.assertEqual(obj.map_coordinates,MARKER)
        self.assertEqual(obj.map_center,CENTER)
        self.assertEqual(obj.map_zoom,15)
        self.assertEqual(obj.map_source,source)
        old=deepcopy(obj.map_source)
        with self.assertRaises(ValidationError):apply_map_import(obj,{**source,'zoom':'invalid'})
        self.assertEqual(obj.map_source,old)
        self.assertEqual(obj.map_coordinates,MARKER)

    def test_fallbacks_and_zero_zoom(self):
        obj=Product(title='Дом',slug='house',map_coordinates=MARKER,map_zoom=0)
        data=product_map(obj)
        self.assertEqual(data['marker'],data['center'])
        self.assertEqual(data['zoom'],0)
        obj.map_zoom=None
        self.assertEqual(product_map(obj)['zoom'],12)
        obj.map_coordinates=''
        self.assertIsNone(product_map(obj))
        obj.map_coordinates='bad'
        self.assertIsNone(product_map(obj))

    @override_settings(YANDEX_MAPS_API_KEY='test-key')
    def test_widget_escapes_and_handles_prefix(self):
        html=str(MapCoordinatesWidget().render('p-map_coordinates',MARKER,{'id':'id_p-map_coordinates'}))
        self.assertIn('data-center-input="id_p-map_center"',html)
        self.assertIn('data-zoom-input="id_p-map_zoom"',html)
        self.assertIn('Загрузить карту',html)


class ObjectMapTests(TestCase):
    def setUp(self):
        self.product=Product.objects.create(title='Дом',slug='map-house',price=None)
        self.data={'title':'Дом','slug':self.product.slug,'currency':'RUB','availability_status':self.product.availability_status,
                   'rating':'0','reviews_count':'0','map_coordinates':MARKER,'map_center':CENTER,'map_zoom':'15'}

    def test_both_forms_save_distinct_pairs_without_rounding(self):
        for form_class in (ProductForm,MultipleProductAdminForm):
            form=form_class(self.data,instance=self.product)
            self.assertTrue(form.is_valid(),form.errors)
            form.save();self.product.refresh_from_db()
            self.assertEqual(self.product.map_coordinates,MARKER)
            self.assertEqual(self.product.map_center,CENTER)
            self.assertEqual(self.product.map_zoom,15)
            self.assertEqual(self.product.slug,'map-house')

    def test_validation_in_both_forms(self):
        for name,value in (('map_coordinates','bad'),('map_center','0,999'),('map_zoom','20'),('map_zoom','-1')):
            for form_class in (ProductForm,MultipleProductAdminForm):
                with self.subTest(name=name,form=form_class):
                    form=form_class({**self.data,name:value},instance=self.product)
                    self.assertFalse(form.is_valid())
                    self.assertIn(name,form.errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.map_coordinates,'')

    def test_public_blank_hidden_and_no_key_link(self):
        url=reverse('catalog:product_detail',args=[self.product.slug])
        self.assertNotContains(self.client.get(url),'id="housing-map"')
        self.product.map_coordinates=MARKER;self.product.map_center=CENTER;self.product.save()
        with override_settings(YANDEX_MAPS_API_KEY=''):
            response=self.client.get(url)
        self.assertContains(response,'id="housing-map"')
        self.assertContains(response,'Открыть в Яндекс Картах')
        self.assertNotContains(response,'Показать карту')
        self.assertNotContains(response,'api-maps.yandex.ru')

    @override_settings(YANDEX_MAPS_API_KEY='test-key')
    def test_public_data_safe_no_source_exposure(self):
        self.product.title='<script>bad</script>'
        self.product.map_coordinates=MARKER;self.product.map_center=CENTER;self.product.map_zoom=15
        self.product.map_source={'ballun':'PRIVATE_SOURCE','file':'PRIVATE_FILE'};self.product.save()
        response=self.client.get(reverse('catalog:product_detail',args=[self.product.slug]))
        self.assertContains(response,'Показать карту')
        self.assertContains(response,r'\u003Cscript\u003Ebad\u003C/script\u003E')
        self.assertNotContains(response,'PRIVATE_SOURCE')
        self.assertNotContains(response,'PRIVATE_FILE')
        self.assertEqual(response.context['housing_map']['center'],['38.887205','44.196131'])

    def test_admin_map_widget_and_source_readonly(self):
        user=get_user_model().objects.create_superuser('map-admin',password='test')
        self.client.force_login(user)
        self.product.map_source={'location':MARKER};self.product.save()
        response=self.client.get(reverse('admin:products_product_change',args=[self.product.pk]))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-object-map-editor')
        self.assertContains(response,'Центр карты')
        self.assertContains(response,'Исходные данные карты JBZoo')
        self.assertNotIn('map_source',response.context['adminform'].form.fields)


class ObjectMapMigrationTests(TransactionTestCase):
    def test_old_data_categories_and_price_preserved(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes()
        before=[('products','0014_product_categories_alter_product_category')]
        after=[('products','0015_product_map_center_product_map_coordinates_and_more')]
        try:
            executor.migrate(before)
            apps=executor.loader.project_state(before).apps
            category=apps.get_model('products','Category').objects.create(title='Адлер',slug='map-adler')
            old=apps.get_model('products','Product').objects.create(title='Дом',slug='before-map',price=None,category_id=category.pk,price_description='<table></table>')
            old.categories.add(category)
            executor=MigrationExecutor(connection);executor.migrate(after)
            obj=executor.loader.project_state(after).apps.get_model('products','Product').objects.get(pk=old.pk)
            self.assertEqual(obj.slug,'before-map')
            self.assertIsNone(obj.price)
            self.assertEqual(list(obj.categories.values_list('pk',flat=True)),[category.pk])
            self.assertEqual(obj.price_description,'<table></table>')
            self.assertEqual(obj.map_coordinates,'')
            self.assertEqual(obj.map_center,'')
            self.assertEqual(obj.map_zoom,12)
        finally:
            MigrationExecutor(connection).migrate(leaves)

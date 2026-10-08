"""Редактор без Яндекс API, с неизменным форматом данных и публичной картой."""
from django.test import SimpleTestCase, override_settings
from apps.products.map_widgets import MapCoordinatesWidget
from apps.products.map_data import product_map
from apps.products.models import Product


class OpenLayersEditorTests(SimpleTestCase):
    @override_settings(YANDEX_MAPS_API_KEY='')
    def test_editor_available_without_yandex_key(self):
        widget=MapCoordinatesWidget()
        html=str(widget.render('map_coordinates','38.887676244734415, 44.19781059487658',{'id':'id_map_coordinates'}))
        self.assertIn('Загрузить карту',html)
        self.assertNotIn('data-api-key',html)
        self.assertNotIn('api-maps.yandex.ru',html)
        self.assertIn('data-tile-url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"',html)
        self.assertIn('OpenStreetMap',html)
        media=str(widget.media)
        self.assertIn('vendor/openlayers/ol.js',media)
        self.assertIn('vendor/openlayers/ol.css',media)
        self.assertIn('map-editor-openlayers.js',media)
        self.assertNotIn('products/js/object-map.js',media)

    @override_settings(YANDEX_MAPS_API_KEY='public-key')
    def test_key_still_used_by_public_card_only(self):
        obj=Product(title='Дом',slug='house',map_coordinates='38.887676244734415, 44.19781059487658',map_center='38.887205,44.196131',map_zoom=15)
        data=product_map(obj)
        self.assertEqual(data['api_key'],'public-key')
        self.assertEqual(data['marker'],['38.887676244734415','44.19781059487658'])
        self.assertEqual(data['center'],['38.887205','44.196131'])

    @override_settings(MAP_EDITOR_TILE_URL='https://example.test/{z}/{x}/{y}.png',MAP_EDITOR_TILE_ATTRIBUTION='Test provider')
    def test_tile_provider_can_be_configured(self):
        html=str(MapCoordinatesWidget().render('map_coordinates','',{'id':'id_map_coordinates'}))
        self.assertIn('https://example.test/{z}/{x}/{y}.png',html)
        self.assertIn('Test provider',html)

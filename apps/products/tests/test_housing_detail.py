"""Публичные разделы, безопасность HTML и совместимость карточки."""
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from apps.products.models import Product, Brand, Location, AttributeType, AttributeValue, ProductAttribute, ProductGalleryImage
from apps.products.housing_detail import housing_context, public_html, phones, SECTIONS
from apps.products.tests.test_prices_html import EXAMPLE


class HousingDetailTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='Гостевой дом',slug='guest-house',price=None)
        self.url = reverse('catalog:product_detail',args=[self.product.slug])

    def test_all_public_fields_and_no_private_data(self):
        self.product.brand = Brand.objects.create(name='Гостиницы',slug='hotels')
        self.product.location = Location.objects.create(name='Ольгинка',slug='olginka')
        self.product.subtitle = 'Отдых у моря'
        self.product.district_text = 'Центральный район'
        self.product.address = 'Морская, 2Б'
        self.product.short_description = '<p>Уютный дом</p>'
        for _, _, fields in SECTIONS:
            for name, _ in fields:
                setattr(self.product,name,f'<p>PUBLIC_{name}</p>')
        self.product.price_description = EXAMPLE
        self.product.contact_name = 'Анна'
        self.product.contact_phone = '+7 (900) 123-45-67; звонить вечером'
        self.product.additional_contact_name = 'Иван'
        self.product.additional_contact_phone = '8 (900) 765-43-21'
        self.product.contact_email = 'host@example.test'
        self.product.internal_notes = 'PRIVATE_INTERNAL'
        self.product.price_description_source = 'PRIVATE_SOURCE'
        self.product.article = 'PRIVATE_ARTICLE'
        self.product.save()
        response = self.client.get(self.url)
        for marker in ['Отдых у моря','Ольгинка','Центральный район','Морская, 2Б','Уютный дом','Анна','Иван','host@example.test','tel:+79001234567','CCUFIJHLHB']:
            self.assertContains(response,marker)
        for _,title,fields in SECTIONS:
            self.assertContains(response,title)
            for name,_ in fields:
                if name!='price_description':self.assertContains(response,f'PUBLIC_{name}')
        self.assertNotContains(response,'PRIVATE_')
        self.assertNotContains(response,'&lt;p&gt;PUBLIC_')
        self.assertContains(response,'Цена по запросу')
        self.assertContains(response,reverse('appointments:car_inquiry',args=[self.product.pk]))
        self.assertNotContains(response,'Заказать это авто')

    def test_empty_sections_contacts_and_attributes_hidden(self):
        response = self.client.get(self.url)
        self.assertNotContains(response,'id="housing-booking"')
        self.assertNotContains(response,'id="housing-contacts"')
        self.assertNotContains(response,'id="housing-amenities"')
        self.assertNotContains(response,'Характеристики не указаны')
        self.assertNotContains(response,'class="housing-detail__navigation"')
        self.assertContains(response,'Нет фото')

    def test_html_restrictions_and_plain_text_paragraphs(self):
        self.product.rooms_description='<script>LEAK_SCRIPT()</script><p onclick="BAD_HANDLER()">Комнаты</p>'
        self.product.booking_conditions='Первый абзац\n\nВторой абзац'
        self.product.meals_description='<p><br></p>'
        self.product.additional_services='<script>ONLY_SCRIPT()</script>'
        self.product.save()
        response=self.client.get(self.url)
        self.assertContains(response,'<p>Комнаты</p>',html=True)
        self.assertContains(response,'<p>Первый абзац</p>',html=True)
        self.assertContains(response,'<p>Второй абзац</p>',html=True)
        self.assertNotContains(response,'LEAK_SCRIPT')
        self.assertNotContains(response,'BAD_HANDLER')
        self.assertNotContains(response,'ONLY_SCRIPT')
        self.assertNotContains(response,'id="housing-meals"')
        self.assertNotContains(response,'id="housing-conditions"')

    def test_grouped_multiple_icons_and_null_value(self):
        kind=AttributeType.objects.create(name='Удобства',slug='amenities',data_type='choice',allow_multiple=True,icon='attributes/types/common.png')
        wifi=AttributeValue.objects.create(attribute_type=kind,value='Wi-Fi',icon='attributes/values/wifi.png')
        pool=AttributeValue.objects.create(attribute_type=kind,value='Бассейн')
        for v in [wifi,pool]:ProductAttribute.objects.create(product=self.product,attribute_type=kind,attribute_value=v)
        other=AttributeType.objects.create(name='Не заполнено',slug='empty-value')
        ProductAttribute.objects.create(product=self.product,attribute_type=other)
        response=self.client.get(self.url)
        self.assertContains(response,'Wi-Fi')
        self.assertContains(response,'Бассейн')
        self.assertContains(response,'/media/attributes/values/wifi.png')
        self.assertContains(response,'/media/attributes/types/common.png')
        self.assertNotContains(response,'Не заполнено')
        self.assertContains(response,'<h3><img src="/media/attributes/types/common.png" alt="" width="24" height="24" loading="lazy">Удобства</h3>',html=True)

    def test_gallery_without_main_photo_uses_first_and_counts_correctly(self):
        ProductGalleryImage.objects.create(product=self.product,image='products/gallery/a.jpg')
        ProductGalleryImage.objects.create(product=self.product,image='products/gallery/b.jpg')
        data=housing_context(self.product)
        self.assertEqual(data['housing_gallery_count'],2)
        self.assertEqual(data['housing_cover'].name,'products/gallery/a.jpg')
        # Avoid reading non-existent image bytes in the template thumbnail engine.
        from unittest.mock import patch
        with patch('easy_thumbnails.templatetags.thumbnail.get_thumbnailer'):
            response=self.client.get(self.url)
        self.assertContains(response,'id="main-image"')
        self.assertNotContains(response,'Нет фото')

    def test_zero_price_and_inactive_object(self):
        self.product.price=0;self.product.save()
        self.assertContains(self.client.get(self.url),'0 ₽')
        self.product.is_active=False;self.product.save()
        self.assertEqual(self.client.get(self.url).status_code,404)


class HousingTextTests(SimpleTestCase):
    def test_plain_text_escapes_markup_and_phone_links_are_unambiguous(self):
        self.assertEqual(public_html(''), '')
        self.assertIn('&amp;',public_html('Море & отдых'))
        self.assertEqual(public_html('<p><br></p>'),'')
        values=phones('+7 (900) 123-45-67, 12345; доб. 10; javascript:bad')
        self.assertEqual(values[0]['href'],'tel:+79001234567')
        self.assertTrue(all(not v['href'] for v in values[1:]))

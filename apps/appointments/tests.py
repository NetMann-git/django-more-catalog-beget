# apps/appointments/tests.py

import json
from datetime import date, time
from unittest.mock import Mock, patch

import requests

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.products.models import Product

from .models import Appointment, WorkingHours, CallbackRequest
from .notifications import (
    send_email_notification,
    send_telegram_notification,
    send_max_notification,
)


class AppointmentModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title="Тестовое платье",
            slug="test-dress",
            price=100000,
        )

        cls.appointment_date = date(2026, 8, 10)
        cls.appointment_time = time(14, 0)

    def create_appointment(self, **kwargs):
        data = {
            "product": self.product,
            "name": "Тестовый клиент",
            "phone": "+7 (999) 123-45-67",
            "email": "test@example.com",
            "date": self.appointment_date,
            "time": self.appointment_time,
            "status": "pending",
        }
        data.update(kwargs)
        return Appointment.objects.create(**data)

    def test_appointment_can_be_created(self):
        appointment = self.create_appointment()

        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(appointment.status, "pending")

    def test_same_slot_cannot_be_booked_twice(self):
        self.create_appointment()

        with self.assertRaises(ValidationError):
            self.create_appointment()

        self.assertEqual(Appointment.objects.count(), 1)

    def test_cancelled_appointment_does_not_block_slot(self):
        self.create_appointment(status="cancelled")

        appointment = self.create_appointment()

        self.assertEqual(Appointment.objects.count(), 2)
        self.assertEqual(appointment.status, "pending")

    def test_confirmed_appointment_blocks_slot(self):
        self.create_appointment(status="confirmed")

        with self.assertRaises(ValidationError):
            self.create_appointment()

        self.assertEqual(Appointment.objects.count(), 1)


class AvailableSlotsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title="Тестовое платье",
            slug="test-dress-slots",
            price=100000,
        )

        cls.appointment_date = date(2026, 8, 10)

        WorkingHours.objects.create(
            day_of_week=cls.appointment_date.weekday(),
            start_time=time(10, 0),
            end_time=time(16, 0),
            is_active=True,
        )

    def test_booked_slot_is_not_available(self):
        Appointment.objects.create(
            product=self.product,
            name="Тестовый клиент",
            phone="+7 (999) 123-45-67",
            date=self.appointment_date,
            time=time(14, 0),
            status="pending",
        )

        from .views import get_available_slots

        response = get_available_slots(
            None,
            self.appointment_date.strftime("%Y-%m-%d"),
        )

        data = json.loads(response.content)

        booked_slot = next(
            slot
            for slot in data["slots"]
            if slot["time"] == "14:00"
        )

        self.assertFalse(booked_slot["available"])

    def test_free_slot_is_available(self):
        from .views import get_available_slots

        response = get_available_slots(
            None,
            self.appointment_date.strftime("%Y-%m-%d"),
        )

        data = json.loads(response.content)

        free_slot = next(
            slot
            for slot in data["slots"]
            if slot["time"] == "14:30"
        )

        self.assertTrue(free_slot["available"])

class CallbackRequestTests(TestCase):
    def test_callback_request_is_saved(self):
        response = self.client.post(
            '/appointments/callback-submit/',
            {'name': 'Иван', 'phone': '+7 (999) 123-45-67'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            'success': True,
            'message': 'Спасибо! Заявка принята. Мы свяжемся с вами в ближайшее время.',
        })
        self.assertEqual(CallbackRequest.objects.count(), 1)
        callback = CallbackRequest.objects.get()
        self.assertEqual(callback.name, 'Иван')
        self.assertEqual(callback.phone, '+7 (999) 123-45-67')
        self.assertEqual(callback.source, 'homepage')

    def test_callback_request_rejects_invalid_phone(self):
        response = self.client.post(
            '/appointments/callback-submit/',
            {'name': 'Иван', 'phone': '123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('phone', response.json()['errors'])
        self.assertEqual(CallbackRequest.objects.count(), 0)

    def test_honeypot_does_not_create_request(self):
        response = self.client.post(
            '/appointments/callback-submit/',
            {'name': 'Bot', 'phone': '+79991234567', 'website': 'https://spam.example'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(CallbackRequest.objects.count(), 0)


class CarInquiryTests(TestCase):
    """Запрос расчёта сохраняет контакт и выбранный автомобиль."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title='Тестовый автомобиль',
            slug='test-car-inquiry',
            price=100000,
        )

    def setUp(self):
        self.url = reverse('appointments:car_inquiry', args=[self.product.pk])

    def test_form_is_available_without_javascript(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый автомобиль')
        self.assertContains(response, 'Ваш город')

    def test_product_page_has_inquiry_link(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.url)
        self.assertContains(response, 'Уточнить условия')
        self.assertContains(response, 'Оставить заявку')
        self.assertNotContains(response, 'Подобрать размер')
        self.assertNotContains(response, 'Таблица размеров')

    def test_order_form_has_own_heading_and_preserves_action(self):
        response = self.client.get(
            self.url + '?type=order',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertContains(response, 'Оставить заявку')
        self.assertContains(response, 'Заявка не подтверждает бронирование')
        self.assertContains(response, f'action="{self.url}?type=order"')

    def test_order_form_opens_without_javascript(self):
        response = self.client.get(self.url + '?type=order')
        self.assertContains(response, 'Оставить заявку')
        self.assertContains(response, f'action="{self.url}?type=order"')

    @patch('apps.appointments.views.send_max_notification')
    @patch('apps.appointments.views.send_telegram_notification')
    @patch('apps.appointments.views.send_email_notification')
    def test_order_without_ajax_opens_success_modal_once(self, *_notifications):
        response = self.client.post(
            self.url + '?type=order',
            {'name': 'Иван', 'phone': '+79991234567', 'city': 'Ростов-на-Дону'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Спасибо!')
        self.assertContains(response, 'Заявка получена. Менеджер свяжется с вами.')
        self.assertNotContains(response, 'aria-labelledby="car-inquiry-title" hidden')
        self.assertEqual(CallbackRequest.objects.filter(source='product_order').count(), 1)

        refreshed = self.client.get(self.product.get_absolute_url())
        self.assertContains(refreshed, 'aria-labelledby="car-inquiry-title" hidden')
        self.assertNotContains(refreshed, '<h2 id="car-inquiry-title">Спасибо!</h2>')

    @patch('apps.appointments.views.send_max_notification')
    @patch('apps.appointments.views.send_telegram_notification')
    @patch('apps.appointments.views.send_email_notification')
    def test_order_submission_notifies_managers_with_product(
        self, email, telegram, max_message,
    ):
        response = self.client.post(
            self.url + '?type=order',
            {'name': 'Иван', 'phone': '+79991234567', 'city': 'Ростов-на-Дону'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        inquiry = CallbackRequest.objects.get(source='product_order')
        self.assertEqual(inquiry.product, self.product)
        email.assert_called_once_with(inquiry)
        telegram.assert_called_once_with(inquiry)
        max_message.assert_called_once_with(inquiry)

    def test_invalid_order_form_keeps_its_kind(self):
        response = self.client.post(
            self.url + '?type=order', {'name': 'Иван', 'phone': '123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, f'action="{self.url}?type=order"', status_code=400)
        self.assertFalse(CallbackRequest.objects.exists())

    @patch('apps.appointments.views.send_max_notification')
    @patch('apps.appointments.views.send_telegram_notification')
    @patch('apps.appointments.views.send_email_notification')
    def test_ajax_submission_saves_car_and_contacts(self, email, telegram, max_message):
        response = self.client.post(
            self.url,
            {
                'name': 'Иван', 'phone': '+7 (999) 123-45-67',
                'city': 'Ростов-на-Дону', 'email': 'ivan@example.com',
                'comment': 'Нужен расчёт доставки',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        inquiry = CallbackRequest.objects.get(source='product_detail')
        self.assertEqual(inquiry.product, self.product)
        self.assertEqual(inquiry.city, 'Ростов-на-Дону')
        self.assertEqual(inquiry.email, 'ivan@example.com')
        self.assertEqual(inquiry.comment, 'Нужен расчёт доставки')
        email.assert_called_once_with(inquiry)
        telegram.assert_called_once_with(inquiry)
        max_message.assert_called_once_with(inquiry)

    def test_missing_city_or_short_phone_does_not_save(self):
        response = self.client.post(
            self.url,
            {'name': 'Иван', 'phone': '123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Ваш город', status_code=400)
        self.assertEqual(CallbackRequest.objects.count(), 0)

    def test_honeypot_does_not_create_inquiry(self):
        response = self.client.post(
            self.url,
            {'website': 'spam.example'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CallbackRequest.objects.count(), 0)

    def test_unknown_product_does_not_accept_inquiry(self):
        url = reverse('appointments:car_inquiry', args=[self.product.pk + 100])
        self.assertEqual(self.client.post(url, {}).status_code, 404)

    @patch('apps.appointments.views.send_max_notification')
    @patch('apps.appointments.views.send_telegram_notification')
    @patch('apps.appointments.views.send_email_notification')
    def test_post_with_csrf_checks_and_without_javascript(self, *_notifications):
        client = Client(enforce_csrf_checks=True)
        response = client.get(self.url)
        token = response.context['csrf_token']
        response = client.post(self.url, {
            'csrfmiddlewaretoken': str(token),
            'name': 'Иван', 'phone': '+7 (999) 123-45-67',
            'city': 'Ростов-на-Дону',
        })
        self.assertRedirects(
            response, self.product.get_absolute_url(),
            fetch_redirect_response=False,
        )
        self.assertEqual(CallbackRequest.objects.count(), 1)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='site@example.com',
        MANAGER_EMAILS=['manager@example.com'],
        SITE_URL='https://carstar-rnd.ru',
    )
    def test_manager_email_contains_car_link_and_contacts(self):
        inquiry = CallbackRequest.objects.create(
            name='Иван', phone='+79991234567', product=self.product,
            city='Ростов-на-Дону', email='ivan@example.com',
            source='product_detail',
        )
        self.assertTrue(send_email_notification(inquiry))
        message = mail.outbox[-1]
        self.assertIn('https://carstar-rnd.ru/catalog/test-car-inquiry/', message.body)
        self.assertIn('Ростов-на-Дону', message.body)
        self.assertIn('ivan@example.com', message.body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='site@example.com',
        MANAGER_EMAILS=['manager@example.com'],
        SITE_URL='https://carstar-rnd.ru',
    )
    def test_order_email_has_order_subject_and_car_link(self):
        inquiry = CallbackRequest.objects.create(
            name='Иван', phone='+79991234567', product=self.product,
            city='Ростов-на-Дону', source='product_order',
        )
        self.assertTrue(send_email_notification(inquiry))
        message = mail.outbox[-1]
        self.assertIn('Заявка на покупку автомобиля', message.subject)
        self.assertIn(self.product.get_absolute_url(), message.body)

    def test_manager_sees_car_and_city_in_inquiry_list(self):
        CallbackRequest.objects.create(
            name='Иван', phone='+79991234567', product=self.product,
            city='Ростов-на-Дону', source='product_detail',
        )
        user = get_user_model().objects.create_user(
            username='car-inquiry-manager', password='test-pass',
        )
        user.profile.role = 'manager'
        user.profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse('appointments:callback_request_list'))
        self.assertContains(response, self.product.get_absolute_url())
        self.assertContains(response, 'Ростов-на-Дону')

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="site@example.com",
    MANAGER_EMAILS=["manager1@example.com", "manager2@example.com"],
)
class CallbackEmailNotificationTests(TestCase):
    def test_send_email_notification(self):
        callback = CallbackRequest.objects.create(
            name="Иван",
            phone="+7 (999) 123-45-67",
        )

        result = send_email_notification(callback)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertEqual(
            message.subject,
            "Новая заявка на обратный звонок от Иван",
        )
        self.assertEqual(
            message.to,
            ["manager1@example.com", "manager2@example.com"],
        )
        self.assertEqual(message.from_email, "site@example.com")
        self.assertIn("Имя: Иван", message.body)
        self.assertIn("Телефон: +7 (999) 123-45-67", message.body)
        self.assertIn("Комментарий: Не указан", message.body)
        self.assertEqual(len(message.alternatives), 1)
        self.assertEqual(message.alternatives[0].mimetype, "text/html")

    @patch(
        "apps.appointments.notifications.EmailMultiAlternatives.send",
        side_effect=ConnectionError("SMTP unavailable"),
    )
    def test_email_error_does_not_raise_and_request_stays_in_db(self, mocked_send):
        callback = CallbackRequest.objects.create(
            name="Иван",
            phone="+7 (999) 123-45-67",
        )

        result = send_email_notification(callback)

        self.assertFalse(result)
        self.assertTrue(CallbackRequest.objects.filter(pk=callback.pk).exists())


@override_settings(
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_MANAGER_CHAT_ID="123456789",
)
class CallbackTelegramNotificationTests(TestCase):
    @override_settings(TELEGRAM_MANAGER_CHAT_ID="111, 222, 111")
    @patch("apps.appointments.notifications.requests.post")
    def test_sends_to_each_unique_chat(self, mocked_post):
        callback = CallbackRequest.objects.create(
            name="Иван", phone="+79991234567",
        )

        self.assertTrue(send_telegram_notification(callback))
        self.assertEqual(
            [call.kwargs["data"]["chat_id"] for call in mocked_post.call_args_list],
            ["111", "222"],
        )

    @override_settings(TELEGRAM_MANAGER_CHAT_ID="111,222")
    @patch("apps.appointments.notifications.requests.post")
    def test_failure_for_first_chat_does_not_block_second(self, mocked_post):
        mocked_post.side_effect = [
            requests.ConnectTimeout("unavailable"),
            Mock(status_code=200),
        ]
        callback = CallbackRequest.objects.create(
            name="Иван", phone="+79991234567",
        )

        self.assertTrue(send_telegram_notification(callback))
        self.assertEqual(mocked_post.call_count, 2)

    @patch("apps.appointments.notifications.requests.post")
    def test_send_telegram_notification(self, mocked_post):
        mocked_post.return_value.raise_for_status.return_value = None
        callback = CallbackRequest.objects.create(
            name="Иван Иванов",
            phone="+7 (999) 123-45-67",
        )

        result = send_telegram_notification(callback)

        self.assertTrue(result)
        mocked_post.assert_called_once()
        args, kwargs = mocked_post.call_args
        self.assertEqual(
            args[0],
            "https://api.telegram.org/bottest-token/sendMessage",
        )
        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(kwargs["data"]["chat_id"], "123456789")
        self.assertEqual(kwargs["data"]["parse_mode"], "MarkdownV2")
        self.assertIn("📞 *Новая заявка на звонок*", kwargs["data"]["text"])
        self.assertIn("Иван Иванов", kwargs["data"]["text"])
        self.assertIn(r"+7 \(999\) 123\-45\-67", kwargs["data"]["text"])
        self.assertIn("Комментарий:* Не указан", kwargs["data"]["text"])

    @patch(
        "apps.appointments.notifications.requests.post",
        side_effect=requests.RequestException("Telegram unavailable"),
    )
    def test_telegram_error_does_not_raise_and_request_stays_in_db(self, mocked_post):
        callback = CallbackRequest.objects.create(
            name="Иван",
            phone="+7 (999) 123-45-67",
        )

        result = send_telegram_notification(callback)

        self.assertFalse(result)
        self.assertTrue(CallbackRequest.objects.filter(pk=callback.pk).exists())


@override_settings(
    MAX_BOT_TOKEN="max-test-token",
    MAX_MANAGER_CHAT_ID="987654321",
)
class CallbackMaxNotificationTests(TestCase):
    @patch("apps.appointments.notifications.requests.post")
    def test_send_max_notification(self, mocked_post):
        mocked_post.return_value.raise_for_status.return_value = None
        callback = CallbackRequest.objects.create(
            name="Иван Иванов",
            phone="+7 (999) 123-45-67",
        )

        result = send_max_notification(callback)

        self.assertTrue(result)
        mocked_post.assert_called_once_with(
            "https://platform-api2.max.ru/messages",
            headers={
                "Authorization": "max-test-token",
                "Content-Type": "application/json",
            },
            params={"chat_id": "987654321"},
            json={
                "text": (
                    "📞 *Новая заявка на звонок*\n"
                    "*Имя:* Иван Иванов\n"
                    "*Телефон:* +7 (999) 123-45-67\n"
                    "*Комментарий:* Не указан"
                ),
                "format": "markdown",
            },
            timeout=10,
        )

    @patch(
        "apps.appointments.notifications.requests.post",
        side_effect=requests.RequestException("MAX unavailable"),
    )
    def test_max_error_does_not_raise_and_request_stays_in_db(self, mocked_post):
        callback = CallbackRequest.objects.create(
            name="Иван",
            phone="+7 (999) 123-45-67",
        )

        result = send_max_notification(callback)

        self.assertFalse(result)
        self.assertTrue(CallbackRequest.objects.filter(pk=callback.pk).exists())

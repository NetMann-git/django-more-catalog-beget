import logging
import re
from html import escape

import requests

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone


logger = logging.getLogger(__name__)


def _housing_inquiry_details(callback_request) -> tuple[str, str]:
    """Детали объекта жилья для уведомления менеджеру, если он выбран."""
    if callback_request.source not in ('product_detail', 'product_order'):
        return '', ''
    product = callback_request.product
    product_title = product.title if product else 'Объект удалён'
    product_url = (
        settings.SITE_URL.rstrip('/') + product.get_absolute_url()
        if product else ''
    )
    details = (
        f'Объект жилья: {product_title}\n'
        f'Ссылка: {product_url}\n'
        f'Город: {callback_request.city}\n'
        f'Email: {callback_request.email or "Не указан"}\n'
    )
    return details, product_url


def send_email_notification(callback_request) -> bool:
    """Отправляет менеджеру уведомление о новой заявке на обратный звонок."""
    manager_emails = getattr(settings, "MANAGER_EMAILS", [])
    if not manager_emails:
        logger.error(
            "Не задан MANAGER_EMAILS: уведомление о заявке #%s не отправлено",
            callback_request.pk,
        )
        return False

    name = callback_request.name.strip() if callback_request.name else "Без имени"
    phone = callback_request.phone.strip()

    comment = callback_request.comment or ""
    comment = comment.strip() or "Не указан"

    created_at = timezone.localtime(callback_request.created_at)
    created_at_text = created_at.strftime("%d.%m.%Y %H:%M")

    if callback_request.source == 'product_order':
        subject = f'Заявка по жилью от {name}'
    elif callback_request.source == 'product_detail':
        subject = f'Вопрос по жилью от {name}'
    else:
        subject = f'Новая заявка на обратный звонок от {name}'
    housing_details, product_url = _housing_inquiry_details(callback_request)
    heading = (
        'Получена заявка по жилью'
        if callback_request.source == 'product_order'
        else 'Получен вопрос по жилью'
        if housing_details else 'Получена новая заявка на обратный звонок'
    )
    html_details = ''
    if housing_details:
        title = (
            callback_request.product.title
            if callback_request.product else 'Объект удалён'
        )
        safe_url = escape(product_url, quote=True)
        html_details = (
            f'<p><strong>Объект жилья:</strong> {escape(title)}</p>'
            f'<p><strong>Ссылка:</strong> '
            f'<a href="{safe_url}">{escape(product_url)}</a></p>'
            f'<p><strong>Город:</strong> {escape(callback_request.city)}</p>'
            f'<p><strong>Email:</strong> {escape(callback_request.email or "Не указан")}</p>'
        )
    text_body = (
        f"{heading}.\n\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"{housing_details}"
        f"Комментарий: {comment}\n"
        f"Дата создания: {created_at_text}\n"
    )
    html_body = (
        f"<h2>{heading}</h2>"
        f"<p><strong>Имя:</strong> {escape(name)}</p>"
        f"<p><strong>Телефон:</strong> {escape(phone)}</p>"
        f"{html_details}"
        f"<p><strong>Комментарий:</strong><br>{escape(comment).replace(chr(10), '<br>')}</p>"
        f"<p><strong>Дата создания:</strong> {escape(created_at_text)}</p>"
    )

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=manager_emails,
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Ошибка отправки email-уведомления о заявке #%s",
            callback_request.pk,
        )
        return False

    logger.info(
        "Email-уведомление о заявке #%s отправлено менеджерам",
        callback_request.pk,
    )
    return True


_MARKDOWN_V2_SPECIAL_CHARS = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}.!\\])")


def _escape_markdown_v2(value) -> str:
    """Экранирует пользовательский текст для Telegram MarkdownV2."""
    return _MARKDOWN_V2_SPECIAL_CHARS.sub(r"\\\1", str(value or ""))


def send_telegram_notification(callback_request) -> bool:
    """Отправляет уведомление каждому чату из списка, разделённого запятыми."""
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = list(dict.fromkeys(
        chat_id.strip()
        for chat_id in str(
            getattr(settings, "TELEGRAM_MANAGER_CHAT_ID", "")
        ).split(",")
        if chat_id.strip()
    ))

    if not bot_token or not chat_ids:
        logger.warning(
            "Telegram-уведомление о заявке #%s не отправлено: "
            "TELEGRAM_BOT_TOKEN или TELEGRAM_MANAGER_CHAT_ID не настроены",
            callback_request.pk,
        )
        return False

    name = callback_request.name.strip() if callback_request.name else "Без имени"
    phone = callback_request.phone.strip()
    comment = getattr(callback_request, "comment", "") or ""
    comment = comment.strip() or "Не указан"

    housing_details, _ = _housing_inquiry_details(callback_request)
    extra = f'*Объект жилья:* {_escape_markdown_v2(housing_details)}\n' if housing_details else ''

    title = (
        "🏠 *Заявка по жилью*\n"
        if callback_request.source == 'product_order'
        else "🏠 *Вопрос по жилью*\n"
        if housing_details else "📞 *Новая заявка на звонок*\n"
    )
    text = (
        title +
        f"*Имя:* {_escape_markdown_v2(name)}\n"
        f"*Телефон:* {_escape_markdown_v2(phone)}\n"
        f"{extra}"
        f"*Комментарий:* {_escape_markdown_v2(comment)}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    sent = False
    for position, chat_id in enumerate(chat_ids, start=1):
        response = None
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "MarkdownV2",
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            status = response.status_code if response is not None else "нет ответа"
            logger.warning(
                "Telegram: заявка #%s не доставлена получателю %s/%s "
                "(%s, HTTP %s)",
                callback_request.pk,
                position,
                len(chat_ids),
                type(error).__name__,
                status,
            )
            continue

        sent = True
        logger.info(
            "Telegram: заявка #%s доставлена получателю %s/%s",
            callback_request.pk,
            position,
            len(chat_ids),
        )

    return sent


def send_max_notification(callback_request) -> bool:
    """Отправляет менеджеру MAX-уведомление о новой заявке."""
    bot_token = getattr(settings, "MAX_BOT_TOKEN", "").strip()
    chat_id = str(getattr(settings, "MAX_MANAGER_CHAT_ID", "")).strip()

    if not bot_token or not chat_id:
        logger.warning(
            "MAX-уведомление о заявке #%s не отправлено: "
            "MAX_BOT_TOKEN или MAX_MANAGER_CHAT_ID не настроены",
            callback_request.pk,
        )
        return False

    name = callback_request.name.strip() if callback_request.name else "Без имени"
    phone = callback_request.phone.strip()
    comment = getattr(callback_request, "comment", "") or ""
    comment = comment.strip() or "Не указан"

    housing_details, _ = _housing_inquiry_details(callback_request)
    extra = f'Объект жилья: {housing_details}' if housing_details else ''

    title = (
        "🏠 *Заявка по жилью*\n"
        if callback_request.source == 'product_order'
        else "🏠 *Вопрос по жилью*\n"
        if housing_details else "📞 *Новая заявка на звонок*\n"
    )
    text = (
        title +
        f"*Имя:* {name}\n"
        f"*Телефон:* {phone}\n"
        f"{extra}"
        f"*Комментарий:* {comment}"
    )

    try:
        response = requests.post(
            "https://platform-api2.max.ru/messages",
            headers={
                "Authorization": bot_token,
                "Content-Type": "application/json",
            },
            params={"chat_id": chat_id},
            json={
                "text": text,
                "format": "markdown",
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Ошибка отправки MAX-уведомления о заявке #%s",
            callback_request.pk,
        )
        return False

    logger.info(
        "MAX-уведомление о заявке #%s отправлено менеджеру",
        callback_request.pk,
    )
    return True

"""Единая группировка полей объекта для менеджера и Django Admin."""

HOUSING_EDITOR_SECTIONS = (
    ("Основное", ("title", "slug", "subtitle", "category", "categories", "brand", "image")),
    ("Расположение", ("location", "district_text", "address", "location_description")),
    ("Контакты", ("contact_name", "contact_phone", "additional_contact_name", "additional_contact_phone", "contact_email")),
    ("Описание и проживание", ("short_description", "description", "rooms_description")),
    ("Питание", ("meals_description",)),
    ("Море и пляж", ("beach_description", "beach_distance_description")),
    ("Условия и услуги", ("special_conditions", "additional_services")),
    ("Бронирование", ("booking_conditions", "checkin_checkout_description")),
    ("Цены и размещение", ("price", "currency", "price_description", "included_services", "paid_services", "extra_beds_description")),
    ("SEO", ("meta_title", "meta_description")),
    ("Публикация", ("is_featured", "is_active", "availability_status", "badges")),
    ("Внутренние данные", ("article", "product_type", "internal_notes")),
)

# config/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.home.views import home
from apps.products.import_views import legacy_item
from apps.home.legal_views import public_offer, privacy_policy, personal_data_consent

urlpatterns = [
    path("properties-list/<slug:slug>.html", legacy_item, name="legacy_item"),
    path('admin/', admin.site.urls),
    path('smart_selects/', include('smart_selects.urls')),  # ДОБАВИТЬ ЭТУ СТРОКУ
    path('', home, name='home'),
    path('terms/', public_offer, name='public_offer'),
    path('privacy/', privacy_policy, name='privacy_policy'),
    path('consent/', personal_data_consent, name='personal_data_consent'),
    path('catalog/', include('apps.products.urls')),
    path('wishlist/', include('apps.wishlist.urls')),
    path('reviews/', include('apps.reviews.urls')),
    path('appointments/', include('apps.appointments.urls')),
    path('size-helper/', include('apps.size_helper.urls')),
    path('account/', include('apps.users.urls')),
    path('account/content/', include('apps.home.urls')),
    path('search/', include('apps.search.urls')),
    path('recommendations/', include('apps.recommendations.urls', namespace='recommendations')),
    path('calculator/', include('apps.calculator.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

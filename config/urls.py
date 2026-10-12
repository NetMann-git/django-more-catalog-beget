# config/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.information.views import material_detail
from apps.information.legacy_urls import LEGACY_MATERIAL_PATHS
from config.seo import robots_txt
from apps.products.sitemap_views import housing_sitemap
from apps.home.views import home
from apps.products.import_views import legacy_item
from apps.products.legacy_urls import LEGACY_PREFIXES
from apps.products.category_urls import LEGACY_CATEGORY_PATHS
from apps.products.category_views import category_detail
from apps.home.legal_views import public_offer, privacy_policy, personal_data_consent

urlpatterns = [
    *[path(url.lstrip('/'), material_detail, {'joomla_id': joomla_id})
      for url, joomla_id in LEGACY_MATERIAL_PATHS.items()],
    path('information/', include('apps.information.urls')),
    path('sitemap.xml', housing_sitemap, name='housing_sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    *[path(url.lstrip("/"), category_detail, {"slug": slug})
      for url, slug in LEGACY_CATEGORY_PATHS.items()],
    *[path(f"{prefix}/<slug:slug>.html", legacy_item, {"prefix": prefix})
      for prefix in LEGACY_PREFIXES
      if prefix not in {"gostevye-doma", "chastnyj-sektor-loo", "properties-list"}],
    path("gostevye-doma/<slug:slug>.html", legacy_item, {"prefix":"gostevye-doma"}),
    path("chastnyj-sektor-loo/<slug:slug>.html", legacy_item, {"prefix":"chastnyj-sektor-loo"}),
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

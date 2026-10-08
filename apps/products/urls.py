# apps/products/urls.py
from django.urls import path
from . import views
from . import attribute_management
from .import_views import item_preview

app_name = "catalog"

urlpatterns = [
    path("manage/<int:product_id>/preview/", item_preview, name="item_preview"),
    path("", views.catalog, name="catalog"),
    
    # Маршруты сравнения (должны быть ПЕРЕД <slug:slug>/)
    path("comparison/", views.comparison_list, name="comparison"),
    path("comparison/add/<int:product_id>/", views.add_to_comparison, name="add_to_comparison"),
    path("comparison/remove/<int:product_id>/", views.remove_from_comparison, name="remove_from_comparison"),
    path("comparison/toggle/<int:product_id>/", views.toggle_comparison_ajax, name="toggle_comparison_ajax"),
    path("clear-recently-viewed-ajax/", views.clear_recently_viewed_ajax, name="clear_recently_viewed_ajax"),
    path("recently-viewed/", views.recently_viewed_list, name="recently_viewed"),
    path("brand/<slug:slug>/", views.brand_detail, name="brand_detail"),
    
    # Управление товарами (менеджер) - ДОБАВИТЬ ЭТОТ БЛОК
    path("manage/", views.product_list_manage, name="product_list_manage"),
    path("manage/attribute-types/", attribute_management.attribute_type_list_manage,
         name="attribute_type_list_manage"),
    path("manage/attribute-types/create/", attribute_management.attribute_type_create,
         name="attribute_type_create"),
    path("manage/attribute-types/<int:type_id>/edit/",
         attribute_management.attribute_type_edit, name="attribute_type_edit"),
    path("manage/attribute-types/<int:type_id>/delete/",
         attribute_management.attribute_type_delete, name="attribute_type_delete"),
    path("manage/attribute-types/<int:type_id>/values/create/",
         attribute_management.attribute_value_create, name="attribute_value_create"),
    path("manage/attribute-types/<int:type_id>/values/<int:value_id>/edit/",
         attribute_management.attribute_value_edit, name="attribute_value_edit"),
    path("manage/attribute-types/<int:type_id>/values/<int:value_id>/delete/",
         attribute_management.attribute_value_delete, name="attribute_value_delete"),
    path("manage/brands/", views.brand_list_manage, name="brand_list_manage"),
    path("manage/brands/create/", views.brand_create, name="brand_create"),
    path("manage/brands/<int:brand_id>/edit/", views.brand_edit, name="brand_edit"),
    path("manage/brands/<int:brand_id>/delete/", views.brand_delete, name="brand_delete"),
    path("create/", views.product_create, name="product_create"),
    path("edit/<int:product_id>/", views.product_edit, name="product_edit"),
    path("delete/<int:product_id>/", views.product_delete, name="product_delete"),
    path('attributes/<int:product_id>/', views.product_attributes, name='product_attributes'),
    path('attribute/delete/<int:attribute_id>/', views.attribute_delete, name='attribute_delete'),

    # Галерея
    path('gallery/add/<int:product_id>/', views.gallery_add, name='gallery_add'),
    path('gallery/delete/<int:image_id>/', views.gallery_delete, name='gallery_delete'),
    
    # Страница товара (должна быть последней)
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]

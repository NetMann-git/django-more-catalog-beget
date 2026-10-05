# apps/products/admin.py

from django.contrib import admin
from django.utils.html import format_html
from easy_thumbnails.files import get_thumbnailer
from .product_attribute_forms import ProductAttributeForm
from .cache import CatalogCache
from .templatetags.price_format import price_format

from .models import (
    Product,
    ProductGalleryImage,
    ProductAttribute,
    Badge,
    Category,
    Location,
)


from .models import AttributeType
from .models import AttributeValue

from .models import Brand

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("logo_tag", "name", "slug", "country", "sort_order")
    list_editable = ("sort_order",)
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "country")
    fieldsets = (
        (None, {"fields": ("name", "slug", "logo", "description", "country", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )

    @admin.display(description="Логотип")
    def logo_tag(self, obj):
        if not obj.logo:
            return format_html('<span style="color:#aaa;">Нет</span>')

        thumbnail = get_thumbnailer(obj.logo).get_thumbnail({
            "size": (60, 40),
            "crop": False,
        })
        return format_html(
            '<img src="{}" style="width:60px;height:40px;object-fit:contain;" alt="" />',
            thumbnail.url,
        )


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1
    fields = ("value", "sort_order")
    ordering = ("sort_order",)

@admin.register(AttributeType)
class AttributeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "data_type")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AttributeValueInline]

    def get_inlines(self, request, obj=None):
        """Free-entry types do not require predefined options."""
        if obj and obj.data_type != 'choice':
            return []
        return super().get_inlines(request, obj)


class ProductGalleryInline(admin.TabularInline):
    model = ProductGalleryImage
    extra = 1
    fields = ("image", "alt", "sort_order")
    ordering = ("sort_order",)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    form = ProductAttributeForm
    extra = 1
    fields = ("attribute_type", "attribute_value", "free_value", "sort_order")
    ordering = ("sort_order",)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Управление географией без изменения типов жилья и характеристик."""

    list_display = ("name", "parent", "slug")
    search_fields = ("name", "slug", "parent__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("parent",)
    list_select_related = ("parent",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    save_on_top = True
    autocomplete_fields = ("location",)
    list_select_related = ("category", "brand", "location")

    def save_related(self, request, form, formsets, change):
        """Invalidate cached attributes after all inline values are saved."""
        super().save_related(request, form, formsets, change)
        CatalogCache.clear_catalog()
    list_display = (
        "title",
        "article",
        "category",
        "location",
        "formatted_price",
        "availability_status",
        "is_featured",
        "is_active",
        "image_tag",
    )
    @admin.display(description="Цена", ordering="price")
    def formatted_price(self, obj):
        """Display grouped prices while retaining numeric sorting."""
        return price_format(obj.price)

    list_filter = (
        "category",
        "location",
        "brand",
        "availability_status",
        "is_featured",
        "is_active",
    )
    search_fields = (
        "title",
        "article",
        "location__name",
        "short_description",
        "description",
    )
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("badges",)
    view_on_site = False

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "title",
                    "slug",
                    "article",
                    "category",
                    "location",
                    "brand",
                    "image",
                )
            },
        ),
        (
            "Описание",
            {
                "fields": (
                    "short_description",
                    "description",
                )
            },
        ),
        (
            "Каталог",
            {
                "fields": (
                    "price",
                    "currency",
                    "badges",
                )
            },
        ),
        (
            "SEO",
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                )
            },
        ),
        (
            "Публикация",
            {
                "fields": (
                    "is_featured",
                    "is_active",
                    "availability_status",
                )
            },
        ),
    )

    inlines = [
        ProductGalleryInline,
        ProductAttributeInline,
    ]

    def image_tag(self, obj):
        if obj.image:
            thumbnail = get_thumbnailer(obj.image).get_thumbnail({
                'size': (80, 60),
                'crop': True,
            })
            return format_html(
                '<img src="{}" style="width:80px; height:60px; object-fit: cover;" />',
                thumbnail.url
            )
        return format_html('<span style="color: #aaa;">Нет фото</span>')
    image_tag.short_description = "Фото"

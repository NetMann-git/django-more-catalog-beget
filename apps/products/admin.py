# apps/products/admin.py

from django.contrib import admin
from django.db.models import Count, OuterRef, Subquery, Value, Q as models_q
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from easy_thumbnails.files import get_thumbnailer
from .product_attribute_forms import ProductAttributeForm
from .attribute_formsets import SingleProductAttributeFormSet
from .multiple_attribute_forms import build_multiple_form, MultipleProductAdminForm, multiple_types
from .category_tree_admin import CategoryTreeChangeList, category_tree_title
from .cache import CatalogCache
from .housing_editor_layout import HOUSING_EDITOR_SECTIONS
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
    list_display = ("logo_tag", "name", "slug", "sort_order")
    list_editable = ("sort_order",)
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "logo", "description", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )

    @admin.display(description="Изображение типа жилья")
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


class AttributeIconPreview:
    @admin.display(description="Предпросмотр")
    def icon_preview(self, obj):
        """Показать сохранённую собственную иконку без генерации миниатюры."""
        if not obj or not obj.icon:
            return "—"
        return format_html(
            '<img src="{}" width="32" height="32" style="object-fit:contain" alt="" />',
            obj.icon.url,
        )


class AttributeValueInline(AttributeIconPreview, admin.TabularInline):
    model = AttributeValue
    extra = 1
    fields = ("value", "icon", "icon_preview", "sort_order")
    readonly_fields = ("icon_preview",)
    ordering = ("sort_order",)

@admin.register(AttributeType)
class AttributeTypeAdmin(AttributeIconPreview, admin.ModelAdmin):
    list_display = ("icon_preview", "name", "slug", "data_type", "allow_multiple")
    list_display_links = ("name",)
    readonly_fields = ("icon_preview",)
    fields = ("name", "slug", "data_type", "allow_multiple", "icon", "icon_preview")
    search_fields = ("name", "slug")
    list_filter = ("data_type", "allow_multiple")
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
    formset = SingleProductAttributeFormSet
    extra = 1
    fields = ("attribute_type", "attribute_value", "free_value", "sort_order")
    ordering = ("sort_order",)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    change_list_template = "admin/products/category/change_list.html"
    list_display = ("tree_title", "elements_count", "parent", "slug", "joomla_id", "sort_order", "is_published")
    list_display_links = None
    sortable_by = ()

    @admin.display(description="Дерево категорий")
    def tree_title(self, obj):
        return category_tree_title(obj)

    @admin.display(description="Элементы")
    def elements_count(self, obj):
        return obj.elements_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            elements_count=Coalesce(Subquery(
                Product.objects.filter(
                    models_q(category_id=OuterRef("pk")) | models_q(categories__pk=OuterRef("pk")),
                ).order_by().annotate(group=Value(1)).values("group")
                .annotate(total=Count("pk", distinct=True)).values("total"),
            ), Value(0)),
        )

    def get_changelist(self, request, **kwargs):
        return CategoryTreeChangeList

    def get_ordering(self, request):
        return ("sort_order", "title", "pk")

    class Media:
        css = {"all": ("products/css/admin/category-tree.css",)}
        js = ("products/js/admin/category-tree.js",)

    search_fields = ("title", "slug")
    list_filter = ("is_published",)
    list_select_related = ("parent",)
    autocomplete_fields = ("parent",)
    readonly_fields = ("joomla_id", "joomla_source")
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
        form.save_multiple(form.instance)
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
        return "Цена по запросу" if obj.price is None else price_format(obj.price)

    list_filter = (
        "category",
        "categories",
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
        "address",
        "contact_name",
        "contact_phone",
        "additional_contact_name",
        "additional_contact_phone",
        "contact_email",
        "short_description",
        "description",
    )
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("badges", "categories")
    view_on_site = False

    # Одинаковые разделы помогают менеджеру и администратору видеть одну структуру.
    fieldsets = tuple((title, {"fields": names}) for title, names in HOUSING_EDITOR_SECTIONS)

    class Media:
        css = {"all": ("products/css/multiple-attributes.css",)}

    def editable_multiple_types(self, request):
        """Сохранить права на характеристики, действовавшие для инлайна."""
        permitted = self.has_change_permission(request) and all(
            request.user.has_perm("products." + action + "_productattribute")
            for action in ("add", "change", "delete")
        )
        return multiple_types() if permitted else []

    def get_form(self, request, obj=None, **kwargs):
        """Декларативные поля нужны до построения формы админкой."""
        kwargs["form"] = build_multiple_form(
            MultipleProductAdminForm, self.editable_multiple_types(request)
        )
        return super().get_form(request, obj, **kwargs)

    readonly_fields = ("price_description_source", "map_source")

    def get_fieldsets(self, request, obj=None):
        """Не изменять общий список fieldsets между запросами пользователей."""
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj and obj.price_description_source:
            fieldsets.append(("Исходный HTML цен (архив)", {"fields": ("price_description_source",), "classes": ("collapse",)}))
        if obj and obj.map_source:
            fieldsets.append(("Исходные данные карты JBZoo", {"fields": ("map_source",), "classes": ("collapse",)}))
        names = tuple(
            f"multiple_attribute_{kind.pk}"
            for kind in self.editable_multiple_types(request)
        )
        if names:
            fieldsets.append(("Множественные характеристики", {"fields": names}))
        return fieldsets

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

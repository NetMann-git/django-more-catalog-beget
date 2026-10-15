from django import forms
from django.contrib import admin
from django.db.models import Q, Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from apps.products.category_tree_admin import CategoryTreeChangeList, category_tree_title
from apps.products.price_widgets import PricesWidget
from .models import InformationCategory, InformationMaterial


class MaterialForm(forms.ModelForm):
    class Meta:
        model = InformationMaterial
        fields = '__all__'
        widgets = {name: PricesWidget(attrs={'rows': 12}) for name in ('intro', 'body', 'extra_body', 'html_insert')}


@admin.register(InformationCategory)
class CategoryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/products/category/change_list.html'
    list_display = ('tree_title', 'elements_count', 'parent', 'slug', 'joomla_id', 'sort_order', 'is_published')
    list_display_links = None
    sortable_by = ()
    list_filter = ('is_published',)
    search_fields = ('title', 'slug')
    readonly_fields = ('joomla_id', 'source')
    list_select_related = ('parent',)
    autocomplete_fields = ('parent',)
    prepopulated_fields = {'slug': ('title',)}

    @admin.display(description='Дерево категорий')
    def tree_title(self, obj):
        return category_tree_title(obj, change_url_name='admin:information_informationcategory_change')

    @admin.display(description='Элементы')
    def elements_count(self, obj):
        return obj.elements_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(elements_count=Coalesce(Subquery(
            InformationMaterial.objects.filter(Q(primary_category_id=OuterRef('pk')) | Q(categories__pk=OuterRef('pk')))
            .order_by().annotate(group=Value(1)).values('group')
            .annotate(total=Count('pk', distinct=True)).values('total')
        ), Value(0)))

    def get_changelist(self, request, **kwargs):
        return CategoryTreeChangeList

    def get_ordering(self, request):
        return ('sort_order', 'title', 'pk')

    class Media:
        css = {'all': ('products/css/admin/category-tree.css',)}
        js = ('products/js/admin/category-tree.js',)


@admin.register(InformationMaterial)
class MaterialAdmin(admin.ModelAdmin):
    form = MaterialForm
    list_display = ('title', 'joomla_id', 'kind', 'primary_category', 'is_active')
    list_filter = ('kind', 'is_active', 'categories')
    search_fields = ('title', 'slug', 'body')
    filter_horizontal = ('categories', 'map_categories')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('joomla_id', 'legacy_url', 'source')

    def get_changeform_initial_data(self, request):
        return {**super().get_changeform_initial_data(request), 'map_mode': 'categories', 'kind': 'info'}
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'kind', 'is_active', 'categories', 'primary_category')}),
        ('Карта жилья', {'fields': ('map_mode', 'map_categories'), 'description': 'Настройки применяются только к материалам типа «Материал с картой».'}),
        ('Содержимое', {'fields': ('subtitle', 'intro', 'body', 'extra_body', 'html_insert', 'image_source')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'meta_keywords', 'meta_robots')}),
        ('Исходники Joomla', {'classes': ('collapse',), 'fields': ('joomla_id', 'legacy_url', 'source')}),
    )

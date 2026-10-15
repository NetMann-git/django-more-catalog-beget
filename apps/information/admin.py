from django import forms
from django.contrib import admin
from django.urls import reverse, path
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render, redirect
from django.utils.html import format_html
from urllib.parse import urlencode
from django.db.models import Q, Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from apps.products.category_tree_admin import CategoryTreeChangeList, category_tree_title
from apps.products.price_widgets import PricesWidget
from .models import InformationCategory, InformationMaterial
from .admin_filters import MaterialCategoryFilter, MaterialCategoryScopeFilter


class MaterialForm(forms.ModelForm):
    class Meta:
        model = InformationMaterial
        fields = '__all__'
        widgets = {name: PricesWidget(attrs={'rows': 12}) for name in ('intro', 'body', 'extra_body', 'html_insert')}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = InformationCategory
        fields = '__all__'
        widgets = {'description': PricesWidget(attrs={'rows': 12})}


@admin.register(InformationCategory)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryForm
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
        url = reverse('admin:information_informationmaterial_changelist') + '?' + urlencode(
            {'material_category': obj.pk, 'category_scope': 'direct'})
        return format_html('<a href="{}">{}</a>', url, obj.elements_count)

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
    list_display = ('title', 'joomla_id', 'kind', 'primary_category', 'is_active', 'preview_link')
    list_filter = ('kind', 'is_active', MaterialCategoryFilter, MaterialCategoryScopeFilter)
    search_fields = ('title', 'slug', 'body')
    filter_horizontal = ('categories', 'map_categories')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('joomla_id', 'legacy_url', 'source', 'preview_link')

    def get_urls(self):
        return [path('<int:object_id>/preview/', self.admin_site.admin_view(self.preview_view),
                     name='information_informationmaterial_preview')] + super().get_urls()

    @admin.display(description='Предпросмотр')
    def preview_link(self, obj):
        if not obj or not obj.pk:
            return 'Сначала сохраните материал.'
        return format_html('<a href="{}" target="_blank" rel="noopener">Открыть предпросмотр</a>',
                           reverse('admin:information_informationmaterial_preview', args=[obj.pk]))

    def preview_view(self, request, object_id):
        from .views import material_detail_context
        obj = self.get_object(request, str(object_id))
        if obj is None:
            raise Http404
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        request.seo_noindex = True
        context = material_detail_context(obj, request.GET.get('object', ''))
        context.update(information_preview=True, preview_edit_url=reverse(
            'admin:information_informationmaterial_change', args=[obj.pk]))
        response = render(request, 'information/detail.html', context)
        response['X-Robots-Tag'] = 'noindex, follow'
        return response

    def _save_preview_response(self, request, obj, default_response):
        if ('_save_preview' in request.POST and '_popup' not in request.POST
                and self.has_view_or_change_permission(request, obj)):
            return redirect('admin:information_informationmaterial_preview', object_id=obj.pk)
        return default_response

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)
        return self._save_preview_response(request, obj, response)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        return self._save_preview_response(request, obj, response)

    def get_changeform_initial_data(self, request):
        return {**super().get_changeform_initial_data(request), 'map_mode': 'categories', 'kind': 'info'}
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'kind', 'is_active', 'preview_link', 'categories', 'primary_category')}),
        ('Карта жилья', {'fields': ('map_mode', 'map_categories'), 'description': 'Настройки применяются только к материалам типа «Материал с картой».'}),
        ('Содержимое', {'fields': ('subtitle', 'intro', 'body', 'extra_body', 'html_insert', 'image_source')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'meta_keywords', 'meta_robots')}),
        ('Исходники Joomla', {'classes': ('collapse',), 'fields': ('joomla_id', 'legacy_url', 'source')}),
    )

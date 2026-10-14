from django import forms
from django.contrib import admin
from apps.products.price_widgets import PricesWidget
from .models import InformationCategory, InformationMaterial


class MaterialForm(forms.ModelForm):
    class Meta:
        model = InformationMaterial
        fields = '__all__'
        widgets = {name: PricesWidget(attrs={'rows': 12}) for name in ('intro', 'body', 'extra_body', 'html_insert')}


@admin.register(InformationCategory)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'joomla_id', 'parent', 'is_published', 'sort_order')
    list_filter = ('is_published',)
    search_fields = ('title', 'slug')
    readonly_fields = ('joomla_id', 'source')


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

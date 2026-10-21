from django.contrib import admin

from core.models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    list_per_page = 20
    search_fields = ('name', 'description')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'name',
        'category',
        'quantity_in_stock',
        'reorder_level',
    )
    list_filter = ('category',)
    list_per_page = 20
    list_select_related = ('category',)
    search_fields = ('sku', 'name')

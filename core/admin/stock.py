from django.contrib import admin

from core.models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'product',
        'movement_type',
        'quantity',
        'performed_by',
        'purchase_order',
        'sales_order',
    )
    list_filter = ('movement_type',)
    list_per_page = 20
    list_select_related = ('product', 'performed_by')
    search_fields = ('product__sku', 'product__name', 'reference_note')

from django.contrib import admin

from core.models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'supplier',
        'status',
        'is_direct',
        'created_by',
        'created_at',
    )
    list_filter = ('status', 'is_direct')
    inlines = (PurchaseOrderItemInline,)


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'product', 'quantity')
    list_select_related = ('purchase_order', 'product')
    search_fields = ('product__sku', 'product__name')

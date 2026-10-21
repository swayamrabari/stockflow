from django.contrib import admin

from core.models import SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'status',
        'is_direct',
        'created_by',
        'created_at',
    )
    list_filter = ('status', 'is_direct')
    list_per_page = 20
    inlines = (SalesOrderItemInline,)


@admin.register(SalesOrderItem)
class SalesOrderItemAdmin(admin.ModelAdmin):
    list_display = ('sales_order', 'product', 'quantity')
    list_per_page = 20
    list_select_related = ('sales_order', 'product')
    search_fields = ('product__sku', 'product__name')

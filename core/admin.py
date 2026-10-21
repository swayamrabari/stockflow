from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from core.models import PurchaseOrder, PurchaseOrderItem, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('StockFlow', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'role', 'is_superuser')
    list_filter = BaseUserAdmin.list_filter + ('role',)


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

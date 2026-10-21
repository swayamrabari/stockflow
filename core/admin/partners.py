from django.contrib import admin

from core.models import Customer, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at')
    list_per_page = 20
    search_fields = ('name', 'email', 'phone')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at')
    list_per_page = 20
    search_fields = ('name', 'email', 'phone')

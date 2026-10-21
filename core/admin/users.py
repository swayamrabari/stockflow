from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from core.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (('StockFlow', {'fields': ('role',)}),)
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'username',
                    'usable_password',
                    'password1',
                    'password2',
                    'role',
                ),
            },
        ),
    )
    list_display = ('username', 'email', 'role', 'is_superuser')
    list_filter = BaseUserAdmin.list_filter + ('role',)

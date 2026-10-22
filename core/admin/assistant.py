from django.contrib import admin

from core.models import Chat, ChatMessage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = False


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('user',)
    list_select_related = ('user',)
    search_fields = ('title', 'user__username')
    readonly_fields = ('session_id', 'created_at', 'updated_at')
    inlines = (ChatMessageInline,)

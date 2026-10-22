import uuid

from django.conf import settings
from django.db import models


class Chat(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assistant_chats',
    )
    session_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    title = models.CharField(max_length=120, default='New chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assistant_chats'
        ordering = ('-updated_at',)

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assistant_chat_messages'
        ordering = ('created_at', 'id')

    def __str__(self):
        return f'{self.chat_id} {self.role}: {self.content[:50]}'

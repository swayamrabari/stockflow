import uuid

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from core.models import Chat, ChatMessage
from core.permissions import AdminRequiredMixin
from core.services.ai_client import AiServiceError, ask_ai


class AssistantView(AdminRequiredMixin, View):
    template_name = 'assistant/index.html'

    def get(self, request):
        chats = Chat.objects.filter(user=request.user)
        chat = None

        if request.GET.get('new') != '1':
            chat_id = request.GET.get('chat')
            if chat_id:
                try:
                    session_id = uuid.UUID(chat_id)
                except (ValueError, TypeError, AttributeError):
                    session_id = None

                if session_id:
                    chat = chats.filter(session_id=session_id).first()

            if chat is None:
                chat = chats.first()

        return render(
            request,
            self.template_name,
            {
                'chats': chats,
                'chat': chat,
                'chat_messages': chat.messages.all() if chat else [],
            },
        )

    def post(self, request):
        message = request.POST.get('message', '').strip()

        if not message:
            messages.error(request, 'Please enter a message.')
            return redirect('assistant')

        if len(message) > 2000:
            messages.error(request, 'Messages cannot be longer than 2000 characters.')
            return redirect('assistant')

        chat = None
        chat_id = request.POST.get('chat_id')
        if chat_id:
            try:
                session_id = uuid.UUID(chat_id)
            except (ValueError, TypeError, AttributeError):
                session_id = None

            if session_id:
                chat = Chat.objects.filter(
                    user=request.user,
                    session_id=session_id,
                ).first()

        if chat is None:
            chat = Chat.objects.create(
                user=request.user,
                title=' '.join(message.split())[:120],
            )

        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.Role.USER,
            content=message,
        )

        try:
            answer = ask_ai(message, str(chat.session_id))
        except AiServiceError as error:
            chat.save(update_fields=['updated_at'])
            messages.error(request, str(error))
            return redirect(f'{reverse("assistant")}?chat={chat.session_id}')

        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.Role.ASSISTANT,
            content=answer,
        )
        chat.save(update_fields=['updated_at'])

        return redirect(f'{reverse("assistant")}?chat={chat.session_id}')

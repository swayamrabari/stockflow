from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.models import Chat, ChatMessage
from core.services.ai_client import AiServiceError
from core.tests.helpers import PASSWORD, User


class AssistantAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('assistant'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("assistant")}',
        )

    def test_staff_user_is_forbidden(self):
        User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.client.login(username='staffer', password=PASSWORD)

        response = self.client.get(reverse('assistant'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Access denied', status_code=403)

    def test_admin_user_is_allowed(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        self.assertEqual(self.client.get(reverse('assistant')).status_code, 200)


class AssistantChatTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

    @patch('core.views.assistant.ask_ai')
    def test_sending_message_creates_chat_and_messages(self, ask_ai):
        ask_ai.return_value = 'Hello from the assistant.'

        response = self.client.post(
            reverse('assistant'),
            {'message': 'Hello'},
        )

        chat = Chat.objects.get()
        self.assertRedirects(
            response,
            f'{reverse("assistant")}?chat={chat.session_id}',
        )
        self.assertEqual(chat.title, 'Hello')
        self.assertEqual(chat.messages.count(), 2)
        self.assertEqual(chat.messages.first().role, ChatMessage.Role.USER)
        self.assertEqual(chat.messages.last().role, ChatMessage.Role.ASSISTANT)
        self.assertEqual(chat.messages.last().content, 'Hello from the assistant.')
        ask_ai.assert_called_once_with('Hello', str(chat.session_id))

    @patch('core.views.assistant.ask_ai')
    def test_follow_up_reuses_the_same_chat(self, ask_ai):
        ask_ai.side_effect = ['First answer.', 'Second answer.']

        self.client.post(reverse('assistant'), {'message': 'First question'})
        chat = Chat.objects.get()
        self.client.post(
            reverse('assistant'),
            {'message': 'Second question', 'chat_id': str(chat.session_id)},
        )

        self.assertEqual(Chat.objects.count(), 1)
        self.assertEqual(chat.messages.count(), 4)
        self.assertEqual(ask_ai.call_count, 2)
        self.assertEqual(ask_ai.call_args.args[1], str(chat.session_id))

    @patch('core.views.assistant.ask_ai')
    def test_ai_failure_shows_error_without_assistant_message(self, ask_ai):
        ask_ai.side_effect = AiServiceError('The assistant is unavailable.')

        response = self.client.post(
            reverse('assistant'),
            {'message': 'Hello'},
            follow=True,
        )

        self.assertContains(response, 'The assistant is unavailable.')
        chat = Chat.objects.get()
        self.assertEqual(chat.messages.count(), 1)
        self.assertEqual(chat.messages.get().role, ChatMessage.Role.USER)

    def test_history_is_rendered(self):
        chat = Chat.objects.create(user=self.admin, title='Stock chat')
        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.Role.USER,
            content='Where is my stock?',
        )
        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.Role.ASSISTANT,
            content='It is in the warehouse.',
        )

        response = self.client.get(
            reverse('assistant'),
            {'chat': str(chat.session_id)},
        )

        self.assertContains(response, 'Stock chat')
        self.assertContains(response, 'Where is my stock?')
        self.assertContains(response, 'It is in the warehouse.')

    @patch('core.views.assistant.ask_ai')
    def test_empty_message_is_rejected(self, ask_ai):
        response = self.client.post(
            reverse('assistant'),
            {'message': '   '},
            follow=True,
        )

        self.assertContains(response, 'Please enter a message.')
        self.assertFalse(Chat.objects.exists())
        ask_ai.assert_not_called()

    @patch('core.views.assistant.ask_ai')
    def test_new_chat_link_opens_blank_conversation(self, ask_ai):
        chat = Chat.objects.create(user=self.admin, title='Old chat')
        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.Role.USER,
            content='Old message',
        )

        response = self.client.get(reverse('assistant'), {'new': '1'})

        self.assertContains(response, 'New conversation')
        self.assertContains(response, 'How can I help?')
        self.assertNotContains(response, 'Old message')
        ask_ai.assert_not_called()

from django.test import TestCase
from django.urls import reverse

from core.models import Category
from core.tests.helpers import PASSWORD, User


class CategoryViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.category = Category.objects.create(
            name='Hardware',
            description='Tools and fasteners',
        )
        self.client.login(username='adminny', password=PASSWORD)

    def test_list_renders_categories(self):
        response = self.client.get(reverse('category_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hardware')

    def test_create_page_renders(self):
        self.assertEqual(
            self.client.get(reverse('category_create')).status_code,
            200,
        )

    def test_staff_user_can_access_create_page(self):
        User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.client.login(username='staffer', password=PASSWORD)

        response = self.client.get(reverse('category_create'))

        self.assertEqual(response.status_code, 200)

    def test_staff_user_sees_add_category_button(self):
        User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.client.login(username='staffer', password=PASSWORD)

        response = self.client.get(reverse('category_list'))

        self.assertContains(response, reverse('category_create'))

    def test_update_page_renders(self):
        response = self.client.get(reverse('category_update', args=[self.category.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hardware')

    def test_delete_page_renders(self):
        response = self.client.get(reverse('category_delete', args=[self.category.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hardware')

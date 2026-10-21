from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import PASSWORD, User


class HomeRedirectTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("home")}',
        )

    def test_staff_user_lands_on_products(self):
        User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.client.login(username='staffer', password=PASSWORD)

        self.assertRedirects(
            self.client.get(reverse('home')),
            reverse('product_list'),
        )

    def test_admin_user_lands_on_the_dashboard(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        self.assertRedirects(
            self.client.get(reverse('home')),
            reverse('dashboard'),
        )


class RegistrationRemovedTests(TestCase):
    def test_register_url_is_not_available(self):
        response = self.client.get('/register/')

        self.assertEqual(response.status_code, 404)

    def test_login_page_does_not_offer_registration(self):
        response = self.client.get(reverse('login'))

        self.assertNotContains(response, '/register/')
        self.assertNotContains(response, 'Create an account')


class AdminUserCreationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='root',
            email='root@example.com',
            password=PASSWORD,
        )
        self.client.force_login(self.admin)

    def test_add_user_form_exposes_username_password_and_role(self):
        response = self.client.get(reverse('admin:core_user_add'))

        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertContains(response, 'name="role"')

    def test_admin_creates_user_with_assigned_password_and_role(self):
        response = self.client.post(
            reverse('admin:core_user_add'),
            {
                'username': 'assigned-user',
                'usable_password': 'true',
                'password1': PASSWORD,
                'password2': PASSWORD,
                'role': User.Role.ADMIN,
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username='assigned-user')
        self.assertEqual(
            response.url,
            reverse('admin:core_user_change', args=[user.pk]),
        )
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.role, User.Role.ADMIN)

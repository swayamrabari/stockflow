from django.test import TestCase
from django.urls import reverse

from core.models import Customer
from core.tests.helpers import PASSWORD, User


class CustomerViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.customer = Customer.objects.create(
            name='Acme Retail',
            email='buyer@acme.test',
            phone='555-0110',
            address='2 Market Street',
        )
        self.client.login(username='adminny', password=PASSWORD)

    def test_list_renders_customers(self):
        response = self.client.get(reverse('customer_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')

    def test_create_page_renders(self):
        response = self.client.get(reverse('customer_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_name"')
        self.assertContains(response, 'id="id_email"')

    def test_create_submits_and_saves_customer(self):
        response = self.client.post(
            reverse('customer_create'),
            {
                'name': 'Beta Retail',
                'email': '',
                'phone': '',
                'address': '',
            },
        )

        self.assertRedirects(response, reverse('customer_list'))
        self.assertTrue(Customer.objects.filter(name='Beta Retail').exists())

    def test_update_page_renders(self):
        response = self.client.get(reverse('customer_update', args=[self.customer.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')

    def test_delete_page_renders(self):
        response = self.client.get(reverse('customer_delete', args=[self.customer.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')

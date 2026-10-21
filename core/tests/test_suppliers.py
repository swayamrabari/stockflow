from django.test import TestCase
from django.urls import reverse

from core.models import Supplier
from core.tests.helpers import PASSWORD, User


class SupplierViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.supplier = Supplier.objects.create(
            name='Acme Supplies',
            email='sales@acme.test',
            phone='555-0100',
            address='1 Industrial Road',
        )
        self.client.login(username='adminny', password=PASSWORD)

    def test_list_renders_suppliers(self):
        response = self.client.get(reverse('supplier_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')

    def test_create_page_renders(self):
        response = self.client.get(reverse('supplier_create'))

        self.assertEqual(response.status_code, 200)
        # The form must actually render its fields, not an empty page.
        self.assertContains(response, 'id="id_name"')
        self.assertContains(response, 'id="id_email"')

    def test_create_submits_and_saves_supplier(self):
        response = self.client.post(
            reverse('supplier_create'),
            {
                'name': 'Beta Ltd',
                'email': '',
                'phone': '',
                'address': '',
            },
        )

        self.assertRedirects(response, reverse('supplier_list'))
        self.assertTrue(Supplier.objects.filter(name='Beta Ltd').exists())

    def test_update_page_renders(self):
        response = self.client.get(reverse('supplier_update', args=[self.supplier.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')

    def test_delete_page_renders(self):
        response = self.client.get(reverse('supplier_delete', args=[self.supplier.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')

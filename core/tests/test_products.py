from django.test import TestCase
from django.urls import reverse

from core.models import Category, Product
from core.tests.helpers import PASSWORD, User


class ProductViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.category = Category.objects.create(name='Hardware')
        self.product = Product.objects.create(
            sku='SKU-1',
            name='Hammer',
            quantity_in_stock=5,
            reorder_level=2,
            category=self.category,
        )
        self.client.login(username='adminny', password=PASSWORD)

    def test_list_renders_products(self):
        response = self.client.get(reverse('product_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hammer')
        self.assertContains(response, 'SKU-1')

    def test_search_filters_products(self):
        response = self.client.get(reverse('product_list'), {'q': 'zzz'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Hammer')

    def test_stock_filter_shows_low_stock_products(self):
        Product.objects.create(
            sku='SKU-0',
            name='Battery',
            quantity_in_stock=1,
            reorder_level=5,
            category=self.category,
        )

        response = self.client.get(reverse('product_list'), {'stock': 'low'})

        self.assertContains(response, 'Battery')
        self.assertNotContains(response, 'Hammer')

    def test_stock_filter_shows_out_of_stock_products(self):
        Product.objects.create(
            sku='SKU-0',
            name='Battery',
            quantity_in_stock=0,
            reorder_level=5,
            category=self.category,
        )

        response = self.client.get(reverse('product_list'), {'stock': 'out'})

        self.assertContains(response, 'Battery')
        self.assertNotContains(response, 'Hammer')

    def test_create_page_renders(self):
        response = self.client.get(reverse('product_create'))

        self.assertEqual(response.status_code, 200)
        # The form must actually render its fields, not an empty page.
        self.assertContains(response, 'id="id_sku"')
        self.assertContains(response, 'name="category"')

    def test_create_submits_and_saves_product(self):
        response = self.client.post(
            reverse('product_create'),
            {
                'sku': 'SKU-2',
                'name': 'Wrench',
                'description': '',
                'category': self.category.pk,
                'reorder_level': 3,
            },
        )

        self.assertRedirects(response, reverse('product_list'))
        self.assertTrue(Product.objects.filter(sku='SKU-2').exists())

    def test_update_page_renders(self):
        response = self.client.get(reverse('product_update', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hammer')

    def test_delete_page_renders(self):
        response = self.client.get(reverse('product_delete', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hammer')

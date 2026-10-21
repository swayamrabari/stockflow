from django.test import TestCase
from django.urls import reverse

from core.models import (
    Category,
    Customer,
    Product,
    PurchaseOrder,
    SalesOrder,
    StockMovement,
    Supplier,
)
from core.tests.helpers import PASSWORD, User


class ListPaginationTests(TestCase):
    page_size = 20
    total_items = 21

    def setUp(self):
        self.user = User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.client.force_login(self.user)

    def assert_paginated(self, url_name):
        first_page = self.client.get(reverse(url_name))

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(
            first_page.context['paginator'].count,
            self.total_items,
        )
        self.assertEqual(
            len(first_page.context['page_obj'].object_list),
            self.page_size,
        )
        self.assertContains(first_page, 'Page 1 of 2')
        self.assertContains(first_page, 'page=2')

        second_page = self.client.get(reverse(url_name), {'page': 2})

        self.assertEqual(
            len(second_page.context['page_obj'].object_list),
            self.total_items - self.page_size,
        )
        self.assertContains(second_page, 'Page 2 of 2')
        self.assertContains(second_page, 'page=1')

    def test_category_list_paginates(self):
        Category.objects.bulk_create(
            [
                Category(name=f'Category {index:02d}')
                for index in range(self.total_items)
            ]
        )

        self.assert_paginated('category_list')

    def test_product_list_paginates(self):
        category = Category.objects.create(name='Hardware')
        Product.objects.bulk_create(
            [
                Product(
                    sku=f'SKU-{index:02d}',
                    name=f'Product {index:02d}',
                    category=category,
                )
                for index in range(self.total_items)
            ]
        )

        self.assert_paginated('product_list')

    def test_supplier_list_paginates(self):
        Supplier.objects.bulk_create(
            [
                Supplier(name=f'Supplier {index:02d}')
                for index in range(self.total_items)
            ]
        )

        self.assert_paginated('supplier_list')

    def test_customer_list_paginates(self):
        Customer.objects.bulk_create(
            [
                Customer(name=f'Customer {index:02d}')
                for index in range(self.total_items)
            ]
        )

        self.assert_paginated('customer_list')

    def test_purchase_order_list_paginates(self):
        supplier = Supplier.objects.create(name='Acme Supplies')
        PurchaseOrder.objects.bulk_create(
            [
                PurchaseOrder(supplier=supplier, created_by=self.user)
                for _ in range(self.total_items)
            ]
        )

        self.assert_paginated('purchase_order_list')

    def test_sales_order_list_paginates(self):
        customer = Customer.objects.create(name='Acme Retail')
        SalesOrder.objects.bulk_create(
            [
                SalesOrder(customer=customer, created_by=self.user)
                for _ in range(self.total_items)
            ]
        )

        self.assert_paginated('sales_order_list')

    def test_stock_movement_list_paginates(self):
        category = Category.objects.create(name='Hardware')
        product = Product.objects.create(
            sku='SKU-1',
            name='Hammer',
            category=category,
        )
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    product=product,
                    performed_by=self.user,
                    movement_type=StockMovement.MovementType.INCOMING,
                    quantity=1,
                )
                for _ in range(self.total_items)
            ]
        )

        self.assert_paginated('stock_movement_list')

    def test_pagination_links_keep_filters(self):
        category = Category.objects.create(name='Hardware')
        Product.objects.bulk_create(
            [
                Product(
                    sku=f'SKU-{index:02d}',
                    name=f'Hammer {index:02d}',
                    category=category,
                )
                for index in range(self.total_items)
            ]
        )

        response = self.client.get(reverse('product_list'), {'q': 'Hammer'})

        self.assertContains(response, 'q=Hammer&amp;page=2')

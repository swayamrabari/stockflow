from django.test import TestCase
from django.urls import reverse

from core.models import (
    Category,
    Customer,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from core.tests.helpers import PASSWORD, User


class TemplateConsistencyTests(TestCase):
    """Guard the shared title/subtitle and table-column conventions."""

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
        self.supplier = Supplier.objects.create(name='Acme Supplies')
        self.customer = Customer.objects.create(name='Acme Retail')
        self.client.login(username='adminny', password=PASSWORD)

    def test_list_pages_render_heading_and_subtitle(self):
        pages = [
            ('category_list', 'Categories'),
            ('product_list', 'Products'),
            ('supplier_list', 'Suppliers'),
            ('customer_list', 'Customers'),
            ('purchase_order_list', 'Purchases'),
            ('sales_order_list', 'Sales'),
            ('stock_movement_list', 'Stock movements'),
        ]

        for url_name, heading in pages:
            with self.subTest(page=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, '<h1 class="text-2xl', count=1)
                self.assertContains(response, f'>{heading}</h1>')

    def test_form_pages_render_a_subtitle(self):
        pages = [
            'category_create',
            'product_create',
            'supplier_create',
            'customer_create',
            'purchase_order_create',
            'sales_order_create',
            'stock_movement_create',
        ]

        for url_name in pages:
            with self.subTest(page=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, '<h1 class="mt-4 text-2xl')
                self.assertContains(response, 'mt-1 text-sm text-neutral-600')

    def test_delete_pages_use_the_same_heading_size(self):
        pages = [
            reverse('category_delete', args=[self.category.pk]),
            reverse('product_delete', args=[self.product.pk]),
            reverse('supplier_delete', args=[self.supplier.pk]),
            reverse('customer_delete', args=[self.customer.pk]),
        ]

        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, '<h1 class="text-2xl')
                self.assertContains(response, 'This action cannot be undone.')

    def test_supplier_page_title_has_no_stray_backslash(self):
        response = self.client.get(reverse('supplier_list'))

        self.assertContains(response, 'Suppliers &middot; StockFlow')
        self.assertNotContains(response, 'StockFlow\\')

    def test_products_table_leads_with_name_then_sku(self):
        response = self.client.get(reverse('product_list'))
        content = response.content.decode()

        self.assertLess(
            content.index('>Name</th>'),
            content.index('>SKU</th>'),
        )

    def test_purchase_order_movements_match_the_ledger_columns(self):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            created_by=self.admin,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=order,
            product=self.product,
            quantity=2,
        )
        order.receive(self.admin)

        ledger = self.client.get(reverse('stock_movement_list'))
        detail = self.client.get(reverse('purchase_order_detail', args=[order.pk]))

        for heading in ('When', 'Product', 'Type', 'Change', 'By', 'Reference'):
            with self.subTest(column=heading):
                self.assertContains(ledger, f'>{heading}</th>')
                self.assertContains(detail, f'>{heading}</th>')

    def test_pricing_is_out_of_scope(self):
        product_page = self.client.get(reverse('product_list'))
        form_page = self.client.get(reverse('product_create'))

        self.assertNotContains(product_page, 'Unit price')
        self.assertNotContains(form_page, 'unit_price')

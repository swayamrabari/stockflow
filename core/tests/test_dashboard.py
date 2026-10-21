from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Category,
    Customer,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    SalesOrderItem,
    StockMovement,
    Supplier,
)
from core.tests.helpers import PASSWORD, User


class DashboardAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("dashboard")}',
        )

    def test_staff_user_is_forbidden(self):
        User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.client.login(username='staffer', password=PASSWORD)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Access denied', status_code=403)

    def test_admin_user_is_allowed(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_superuser_is_allowed(self):
        User.objects.create_superuser(
            username='root',
            password=PASSWORD,
        )
        self.client.login(username='root', password=PASSWORD)

        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)


class DashboardContentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.category = Category.objects.create(name='Hardware')
        self.supplier = Supplier.objects.create(name='Acme Supplies')
        self.customer = Customer.objects.create(name='Beta Retail')

        self.out_of_stock = Product.objects.create(
            sku='SKU-0',
            name='Battery',
            quantity_in_stock=0,
            reorder_level=5,
            category=self.category,
        )
        self.low_stock = Product.objects.create(
            sku='SKU-1',
            name='Hammer',
            quantity_in_stock=3,
            reorder_level=10,
            category=self.category,
        )
        self.healthy = Product.objects.create(
            sku='SKU-2',
            name='Ladder',
            quantity_in_stock=50,
            reorder_level=10,
            category=self.category,
        )

        self.client.login(username='adminny', password=PASSWORD)

    def test_dashboard_shows_inventory_summary(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['product_count'], 3)
        self.assertEqual(response.context['total_units'], 53)
        self.assertEqual(response.context['low_stock_count'], 2)
        self.assertEqual(response.context['out_of_stock_count'], 1)

        low_stock_names = [
            product.name for product in response.context['low_stock_products']
        ]
        self.assertEqual(low_stock_names, ['Battery', 'Hammer'])

        self.assertContains(response, 'Pending purchases')
        self.assertContains(response, 'Pending dispatches')
        self.assertContains(response, 'Low stock alerts')
        self.assertContains(response, 'Out of stock')
        self.assertNotContains(response, 'Pending Orders')
        self.assertNotContains(response, 'Needs action')
        self.assertNotContains(response, 'Blocked by stock')
        self.assertNotContains(response, 'Stock by category')
        self.assertNotContains(response, 'Last 7 days')

    def test_dashboard_shows_pending_purchase_metrics(self):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            created_by=self.admin,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=order,
            product=self.out_of_stock,
            quantity=10,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.context['pending_purchase_count'], 1)
        self.assertEqual(response.context['pending_purchase_units'], 10)
        self.assertIsNone(response.context.get('pending_purchases'))
        self.assertContains(response, 'Pending purchases')
        self.assertContains(response, '10 units')
        self.assertNotContains(response, 'Pending Orders')

    def test_dashboard_shows_pending_dispatch_metrics(self):
        short_order = SalesOrder.objects.create(
            customer=self.customer,
            created_by=self.admin,
        )
        SalesOrderItem.objects.create(
            sales_order=short_order,
            product=self.out_of_stock,
            quantity=4,
        )

        ready_order = SalesOrder.objects.create(
            customer=self.customer,
            created_by=self.admin,
        )
        SalesOrderItem.objects.create(
            sales_order=ready_order,
            product=self.healthy,
            quantity=2,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.context['pending_sales_count'], 2)
        self.assertEqual(response.context['pending_sales_units'], 6)
        self.assertIsNone(response.context.get('pending_sales'))

        self.assertContains(response, 'Pending dispatches')
        self.assertContains(response, '6 units')
        self.assertContains(response, 'Short stock')
        self.assertContains(response, 'Ready')
        self.assertNotContains(response, 'Pending Orders')
        self.assertNotContains(response, 'Blocked by stock')

    def test_dashboard_shows_recent_orders_and_movements(self):
        purchase = PurchaseOrder.objects.create(
            supplier=self.supplier,
            created_by=self.admin,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=purchase,
            product=self.healthy,
            quantity=5,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=purchase,
            product=self.low_stock,
            quantity=1,
        )

        sale = SalesOrder.objects.create(
            customer=self.customer,
            created_by=self.admin,
        )
        SalesOrderItem.objects.create(
            sales_order=sale,
            product=self.healthy,
            quantity=2,
        )
        SalesOrderItem.objects.create(
            sales_order=sale,
            product=self.low_stock,
            quantity=1,
        )

        movement = StockMovement.record(
            product=self.healthy,
            quantity=5,
            movement_type=StockMovement.MovementType.INCOMING,
            user=self.admin,
            note='Opening count',
        )

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Recent orders')
        self.assertContains(response, 'Acme Supplies')
        self.assertContains(response, 'Beta Retail')
        self.assertContains(response, 'Recent stock movements')
        self.assertContains(response, 'Opening count')
        self.assertContains(response, movement.signed_quantity)
        self.assertContains(response, '2 Items')

        expected_time = timezone.localtime(movement.created_at).strftime(
            '%H:%M %d/%m/%Y'
        )
        self.assertContains(response, expected_time)
        self.assertNotContains(response, 'ago')

    def test_dashboard_shows_empty_states(self):
        Product.objects.all().delete()

        response = self.client.get(reverse('dashboard'))

        self.assertContains(
            response,
            'All products are above their reorder level.',
        )
        self.assertContains(response, 'No purchase orders yet.')
        self.assertContains(response, 'No sales orders yet.')
        self.assertContains(response, 'No stock movements recorded yet.')
        self.assertNotContains(response, 'No purchases waiting to be received.')
        self.assertNotContains(response, 'No sales waiting to be dispatched.')

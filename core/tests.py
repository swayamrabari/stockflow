from django.contrib.auth import get_user_model
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

User = get_user_model()

PASSWORD = 'Zx9-qLm4-tRp7'


class RegisterTests(TestCase):
    def test_register_creates_staff_user_and_logs_them_in(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'newbie',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )

        self.assertRedirects(
            response,
            reverse('home'),
            fetch_redirect_response=False,
        )

        user = User.objects.get(username='newbie')
        self.assertEqual(user.role, User.Role.STAFF)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)


class AuthTemplateTests(TestCase):
    def test_register_page_renders_styled_inputs(self):
        response = self.client.get(reverse('register'))

        self.assertContains(response, 'id="id_password1"')
        self.assertContains(response, 'name="password2"')
        self.assertContains(response, 'type="password"')

    def test_register_errors_show_on_the_field(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'newbie',
                'password1': PASSWORD,
                'password2': 'something-else',
            },
        )

        self.assertEqual(response.status_code, 200)
        # username is repopulated, and the failing field gets the thicker border
        self.assertContains(response, 'value="newbie"')
        self.assertContains(response, 'class="border-2"')


class DashboardAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}",
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


class HomeRedirectTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('home')}",
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
        response = self.client.get(
            reverse('category_update', args=[self.category.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hardware')

    def test_delete_page_renders(self):
        response = self.client.get(
            reverse('category_delete', args=[self.category.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hardware')


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
        response = self.client.get(
            reverse('product_update', args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hammer')

    def test_delete_page_renders(self):
        response = self.client.get(
            reverse('product_delete', args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hammer')


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
        response = self.client.get(
            reverse('supplier_update', args=[self.supplier.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')

    def test_delete_page_renders(self):
        response = self.client.get(
            reverse('supplier_delete', args=[self.supplier.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')


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
        response = self.client.get(
            reverse('customer_update', args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')

    def test_delete_page_renders(self):
        response = self.client.get(
            reverse('customer_delete', args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')


class PurchaseOrderViewsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.category = Category.objects.create(name='Hardware')
        self.supplier = Supplier.objects.create(name='Acme Supplies')
        self.hammer = Product.objects.create(
            sku='SKU-1',
            name='Hammer',
            quantity_in_stock=5,
            reorder_level=2,
            category=self.category,
        )
        self.wrench = Product.objects.create(
            sku='SKU-2',
            name='Wrench',
            quantity_in_stock=5,
            reorder_level=2,
            category=self.category,
        )
        self.client.login(username='staffer', password=PASSWORD)

    def build_post_data(self, items, is_direct=False):
        """Render formset POST data for the given (product, qty) rows."""
        data = {
            'supplier': self.supplier.pk,
            'is_direct': 'on' if is_direct else '',
            'items-TOTAL_FORMS': str(len(items)),
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
        }

        for index, (product, quantity) in enumerate(items):
            data[f'items-{index}-product'] = product.pk
            data[f'items-{index}-quantity'] = quantity

        return data

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(reverse('purchase_order_list'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('purchase_order_list')}",
        )

    def test_create_page_renders_supplier_and_item_formset(self):
        response = self.client.get(reverse('purchase_order_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="supplier"')
        self.assertContains(response, 'name="items-TOTAL_FORMS"')
        self.assertContains(response, 'name="items-0-product"')

    def test_create_saves_order_with_multiple_items(self):
        response = self.client.post(
            reverse('purchase_order_create'),
            self.build_post_data(
                [
                    (self.hammer, '3'),
                    (self.wrench, '1'),
                ]
            ),
        )

        self.assertRedirects(response, reverse('purchase_order_list'))

        order = PurchaseOrder.objects.get()
        self.assertEqual(order.supplier, self.supplier)
        self.assertEqual(order.created_by, self.staff)
        self.assertEqual(order.status, PurchaseOrder.Status.PENDING)

        items = list(order.items.order_by('pk'))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].product, self.hammer)
        self.assertEqual(items[0].quantity, 3)

    def test_create_requires_at_least_one_item(self):
        data = {
            'supplier': self.supplier.pk,
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-product': '',
            'items-0-quantity': '',
        }

        response = self.client.post(reverse('purchase_order_create'), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PurchaseOrder.objects.exists())

    def test_create_rejects_the_same_product_twice(self):
        response = self.client.post(
            reverse('purchase_order_create'),
            self.build_post_data(
                [
                    (self.hammer, '3'),
                    (self.hammer, '2'),
                ]
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already in the order')
        self.assertFalse(PurchaseOrder.objects.exists())

    def test_create_rejects_non_positive_quantity(self):
        response = self.client.post(
            reverse('purchase_order_create'),
            self.build_post_data([(self.hammer, '0')]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quantity must be greater than zero')
        self.assertFalse(PurchaseOrder.objects.exists())

    def test_list_renders_orders(self):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            created_by=self.staff,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=order,
            product=self.hammer,
            quantity=3,
        )

        response = self.client.get(reverse('purchase_order_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')
        self.assertContains(response, 'Pending')

    def test_list_filters_by_status(self):
        pending = self.create_order([(self.hammer, 1)])
        received = self.create_order([(self.wrench, 1)], receive=True)

        response = self.client.get(
            reverse('purchase_order_list'), {'status': 'received'}
        )

        self.assertContains(response, f'#{received.pk}')
        self.assertNotContains(response, f'#{pending.pk}')

    def test_list_filters_by_supplier_search(self):
        other_supplier = Supplier.objects.create(name='Beta Ltd')
        order = self.create_order([(self.hammer, 1)])
        other_order = PurchaseOrder.objects.create(
            supplier=other_supplier,
            created_by=self.staff,
        )

        response = self.client.get(reverse('purchase_order_list'), {'q': 'Acme'})

        self.assertContains(response, f'#{order.pk}')
        self.assertNotContains(response, f'#{other_order.pk}')

    def test_list_filters_by_order_number(self):
        order = self.create_order([(self.hammer, 1)])
        other_order = self.create_order([(self.wrench, 1)])

        response = self.client.get(
            reverse('purchase_order_list'), {'q': str(order.pk)}
        )

        self.assertContains(response, f'#{order.pk}')
        self.assertNotContains(response, f'#{other_order.pk}')

    def test_list_filters_by_date(self):
        self.create_order([(self.hammer, 1)])

        response = self.client.get(
            reverse('purchase_order_list'), {'date_from': '2999-01-01'}
        )

        self.assertContains(response, 'No purchases')

    def test_create_page_renders_live_summary_and_direct_toggle(self):
        response = self.client.get(reverse('purchase_order_create'))

        self.assertContains(response, 'id="summary-lines"')
        self.assertContains(response, 'id="summary-units"')
        self.assertContains(response, 'name="is_direct"')

    def test_standard_order_leaves_stock_untouched(self):
        response = self.client.post(
            reverse('purchase_order_create'),
            self.build_post_data([(self.hammer, '3')]),
        )

        self.assertRedirects(response, reverse('purchase_order_list'))

        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 5)

        order = PurchaseOrder.objects.get()
        self.assertEqual(order.status, PurchaseOrder.Status.PENDING)
        self.assertIsNone(order.received_at)
        self.assertFalse(StockMovement.objects.exists())

    def test_direct_order_receives_stock_on_creation(self):
        response = self.client.post(
            reverse('purchase_order_create'),
            self.build_post_data(
                [
                    (self.hammer, '3'),
                    (self.wrench, '2'),
                ],
                is_direct=True,
            ),
        )

        self.assertRedirects(response, reverse('purchase_order_list'))

        self.hammer.refresh_from_db()
        self.wrench.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 8)
        self.assertEqual(self.wrench.quantity_in_stock, 7)

        order = PurchaseOrder.objects.get()
        self.assertEqual(order.status, PurchaseOrder.Status.RECEIVED)
        self.assertIsNotNone(order.received_at)

        movements = list(order.stock_movements.order_by('pk'))
        self.assertEqual(len(movements), 2)
        self.assertEqual(movements[0].product, self.hammer)
        self.assertEqual(movements[0].quantity, 3)
        self.assertEqual(movements[0].performed_by, self.staff)
        self.assertEqual(
            movements[0].movement_type,
            StockMovement.MovementType.INCOMING,
        )

    def test_direct_order_still_requires_an_item(self):
        response = self.client.post(
            reverse('purchase_order_create'),
            {
                'supplier': self.supplier.pk,
                'is_direct': 'on',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': '',
                'items-0-quantity': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PurchaseOrder.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def create_order(self, items=None, is_direct=False, receive=False):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            created_by=self.staff,
            is_direct=is_direct,
        )

        for product, quantity in items or []:
            PurchaseOrderItem.objects.create(
                purchase_order=order,
                product=product,
                quantity=quantity,
            )

        if receive:
            order.receive(self.staff)

        return order

    def test_detail_page_renders_items(self):
        order = self.create_order([(self.hammer, 2)])

        response = self.client.get(
            reverse('purchase_order_detail', args=[order.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')
        self.assertContains(response, 'Hammer')

    def test_update_page_renders_existing_items(self):
        order = self.create_order([(self.hammer, 2)])

        response = self.client.get(
            reverse('purchase_order_update', args=[order.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit purchase')
        self.assertContains(response, 'name="items-0-id"')

    def test_update_edits_items_and_adds_a_row(self):
        order = self.create_order([(self.hammer, 2)])
        item = order.items.get()

        response = self.client.post(
            reverse('purchase_order_update', args=[order.pk]),
            {
                'supplier': self.supplier.pk,
                'is_direct': '',
                'items-TOTAL_FORMS': '2',
                'items-INITIAL_FORMS': '1',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-id': item.pk,
                'items-0-product': self.hammer.pk,
                'items-0-quantity': '5',
                'items-1-product': self.wrench.pk,
                'items-1-quantity': '1',
            },
        )

        self.assertRedirects(
            response,
            reverse('purchase_order_detail', args=[order.pk]),
        )

        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)
        self.assertEqual(order.items.count(), 2)

    def test_update_can_delete_an_item(self):
        order = self.create_order(
            [
                (self.hammer, 2),
                (self.wrench, 1),
            ]
        )
        hammer_item, wrench_item = order.items.order_by('pk')

        response = self.client.post(
            reverse('purchase_order_update', args=[order.pk]),
            {
                'supplier': self.supplier.pk,
                'is_direct': '',
                'items-TOTAL_FORMS': '2',
                'items-INITIAL_FORMS': '2',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-id': hammer_item.pk,
                'items-0-product': self.hammer.pk,
                'items-0-quantity': '2',
                'items-0-DELETE': 'on',
                'items-1-id': wrench_item.pk,
                'items-1-product': self.wrench.pk,
                'items-1-quantity': '1',
            },
        )

        self.assertRedirects(
            response,
            reverse('purchase_order_detail', args=[order.pk]),
        )

        remaining = list(order.items.order_by('pk'))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].product, self.wrench)

    def test_update_rejects_the_same_product_twice(self):
        order = self.create_order([(self.hammer, 2)])
        item = order.items.get()

        response = self.client.post(
            reverse('purchase_order_update', args=[order.pk]),
            {
                'supplier': self.supplier.pk,
                'is_direct': '',
                'items-TOTAL_FORMS': '2',
                'items-INITIAL_FORMS': '1',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-id': item.pk,
                'items-0-product': self.hammer.pk,
                'items-0-quantity': '2',
                'items-1-product': self.hammer.pk,
                'items-1-quantity': '1',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already in the order')

    def test_received_order_cannot_be_edited(self):
        order = self.create_order([(self.hammer, 2)], receive=True)

        response = self.client.get(
            reverse('purchase_order_update', args=[order.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_receive_action_updates_stock_once(self):
        order = self.create_order([(self.hammer, 3)])
        url = reverse('purchase_order_receive', args=[order.pk])

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('purchase_order_detail', args=[order.pk]),
        )

        order.refresh_from_db()
        self.hammer.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.RECEIVED)
        self.assertEqual(self.hammer.quantity_in_stock, 8)
        self.assertEqual(StockMovement.objects.count(), 1)

        # Posting again is a harmless no-op.
        self.client.post(url)

        order.refresh_from_db()
        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 8)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_admin_can_delete_a_pending_order(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        order = self.create_order([(self.hammer, 1)])

        response = self.client.post(
            reverse('purchase_order_delete', args=[order.pk])
        )

        self.assertRedirects(response, reverse('purchase_order_list'))
        self.assertFalse(PurchaseOrder.objects.filter(pk=order.pk).exists())

    def test_staff_user_cannot_reach_the_delete_page(self):
        order = self.create_order([(self.hammer, 1)])

        response = self.client.get(
            reverse('purchase_order_delete', args=[order.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_received_order_cannot_be_deleted(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        order = self.create_order([(self.hammer, 1)], receive=True)

        response = self.client.get(
            reverse('purchase_order_delete', args=[order.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PurchaseOrder.objects.filter(pk=order.pk).exists())


class SalesOrderViewsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.category = Category.objects.create(name='Hardware')
        self.customer = Customer.objects.create(name='Acme Retail')
        self.hammer = Product.objects.create(
            sku='SKU-1',
            name='Hammer',
            quantity_in_stock=5,
            reorder_level=2,
            category=self.category,
        )
        self.wrench = Product.objects.create(
            sku='SKU-2',
            name='Wrench',
            quantity_in_stock=5,
            reorder_level=2,
            category=self.category,
        )
        self.client.login(username='staffer', password=PASSWORD)

    def build_post_data(self, items, is_direct=False):
        """Render formset POST data for the given (product, qty) rows."""
        data = {
            'customer': self.customer.pk,
            'is_direct': 'on' if is_direct else '',
            'items-TOTAL_FORMS': str(len(items)),
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
        }

        for index, (product, quantity) in enumerate(items):
            data[f'items-{index}-product'] = product.pk
            data[f'items-{index}-quantity'] = quantity

        return data

    def create_order(self, items=None, dispatch=False):
        order = SalesOrder.objects.create(
            customer=self.customer,
            created_by=self.staff,
        )

        for product, quantity in items or []:
            SalesOrderItem.objects.create(
                sales_order=order,
                product=product,
                quantity=quantity,
            )

        if dispatch:
            order.dispatch(self.staff)

        return order

    def test_create_page_renders_customer_and_item_formset(self):
        response = self.client.get(reverse('sales_order_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="customer"')
        self.assertContains(response, 'name="is_direct"')
        self.assertContains(response, 'Direct / local sale')
        self.assertContains(response, 'name="items-TOTAL_FORMS"')
        self.assertContains(response, 'name="items-0-product"')

    def test_create_saves_order_with_multiple_items(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data(
                [
                    (self.hammer, '3'),
                    (self.wrench, '1'),
                ]
            ),
        )

        self.assertRedirects(response, reverse('sales_order_list'))

        order = SalesOrder.objects.get()
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.created_by, self.staff)
        self.assertEqual(order.status, SalesOrder.Status.PENDING)

        items = list(order.items.order_by('pk'))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].product, self.hammer)
        self.assertEqual(items[0].quantity, 3)

    def test_create_requires_at_least_one_item(self):
        data = self.build_post_data([(self.hammer, '')])

        response = self.client.post(reverse('sales_order_create'), data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SalesOrder.objects.exists())

    def test_create_rejects_the_same_product_twice(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data(
                [
                    (self.hammer, '3'),
                    (self.hammer, '2'),
                ]
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already in the order')
        self.assertFalse(SalesOrder.objects.exists())

    def test_create_rejects_non_positive_quantity(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data([(self.hammer, '0')]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quantity must be greater than zero')
        self.assertFalse(SalesOrder.objects.exists())

    def test_standard_order_leaves_stock_untouched(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data([(self.hammer, '3')]),
        )

        self.assertRedirects(response, reverse('sales_order_list'))

        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 5)

        order = SalesOrder.objects.get()
        self.assertEqual(order.status, SalesOrder.Status.PENDING)
        self.assertIsNone(order.dispatched_at)
        self.assertFalse(StockMovement.objects.exists())

    def test_direct_sale_dispatches_on_creation(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data(
                [
                    (self.hammer, '3'),
                    (self.wrench, '2'),
                ],
                is_direct=True,
            ),
        )

        self.assertRedirects(response, reverse('sales_order_list'))

        order = SalesOrder.objects.get()
        self.assertTrue(order.is_direct)
        self.assertEqual(order.status, SalesOrder.Status.DISPATCHED)
        self.assertIsNotNone(order.dispatched_at)

        self.hammer.refresh_from_db()
        self.wrench.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 2)
        self.assertEqual(self.wrench.quantity_in_stock, 3)

        self.assertEqual(StockMovement.objects.count(), 2)

    def test_direct_sale_shortage_blocks_creation(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data([(self.hammer, '9')], is_direct=True),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This direct sale cannot be completed')
        self.assertContains(response, '9 requested, only 5')
        self.assertContains(response, 'switch off Direct / local sale')
        self.assertNotContains(response, 'Continue anyway')
        self.assertFalse(SalesOrder.objects.exists())

        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 5)
        self.assertFalse(StockMovement.objects.exists())

    def test_direct_sale_shortage_cannot_be_forced_with_confirm(self):
        data = self.build_post_data([(self.hammer, '9')], is_direct=True)
        data['confirm'] = '1'

        response = self.client.post(reverse('sales_order_create'), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This direct sale cannot be completed')
        self.assertFalse(SalesOrder.objects.exists())

        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 5)

    def test_pending_sale_shortage_warns_before_saving(self):
        response = self.client.post(
            reverse('sales_order_create'),
            self.build_post_data([(self.hammer, '9')]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Not enough stock for some items')
        self.assertContains(response, 'Continue anyway')
        self.assertContains(response, 'stays pending until it is')
        self.assertFalse(SalesOrder.objects.exists())

    def test_pending_sale_shortage_confirm_saves_order(self):
        data = self.build_post_data([(self.hammer, '9')])
        data['confirm'] = '1'

        response = self.client.post(
            reverse('sales_order_create'), data, follow=True
        )

        self.assertContains(response, 'created')

        order = SalesOrder.objects.get()
        self.assertFalse(order.is_direct)
        self.assertEqual(order.status, SalesOrder.Status.PENDING)

        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 5)
        self.assertFalse(StockMovement.objects.exists())

    def test_list_renders_orders(self):
        self.create_order([(self.hammer, 3)])

        response = self.client.get(reverse('sales_order_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')
        self.assertContains(response, 'Pending')

    def test_list_marks_pending_order_as_ready_when_stock_covers_it(self):
        self.create_order([(self.hammer, 3)])

        response = self.client.get(reverse('sales_order_list'))

        self.assertContains(response, 'Ready to dispatch')
        self.assertNotContains(response, 'Short stock')

    def test_list_marks_pending_order_as_short_when_stock_is_missing(self):
        self.create_order([(self.hammer, 9)])

        response = self.client.get(reverse('sales_order_list'))

        self.assertContains(response, 'Short stock')
        self.assertNotContains(response, 'Ready to dispatch')

    def test_list_does_not_show_stock_badge_for_dispatched_orders(self):
        self.create_order([(self.hammer, 1)], dispatch=True)

        response = self.client.get(reverse('sales_order_list'))

        self.assertNotContains(response, 'Ready to dispatch')
        self.assertNotContains(response, 'Short stock')

    def test_list_filters_by_status(self):
        pending = self.create_order([(self.hammer, 1)])
        dispatched = self.create_order([(self.wrench, 1)], dispatch=True)

        response = self.client.get(
            reverse('sales_order_list'), {'status': 'dispatched'}
        )

        self.assertContains(response, f'#{dispatched.pk}')
        self.assertNotContains(response, f'#{pending.pk}')

    def test_list_filters_by_customer_search(self):
        other_customer = Customer.objects.create(name='Beta Retail')
        order = self.create_order([(self.hammer, 1)])
        other_order = SalesOrder.objects.create(
            customer=other_customer,
            created_by=self.staff,
        )

        response = self.client.get(reverse('sales_order_list'), {'q': 'Acme'})

        self.assertContains(response, f'#{order.pk}')
        self.assertNotContains(response, f'#{other_order.pk}')

    def test_dispatch_removes_stock_and_records_movements(self):
        order = self.create_order([(self.hammer, 2), (self.wrench, 3)])

        response = self.client.post(
            reverse('sales_order_dispatch', args=[order.pk])
        )

        self.assertRedirects(
            response,
            reverse('sales_order_detail', args=[order.pk]),
        )

        order.refresh_from_db()
        self.hammer.refresh_from_db()
        self.wrench.refresh_from_db()

        self.assertEqual(order.status, SalesOrder.Status.DISPATCHED)
        self.assertIsNotNone(order.dispatched_at)
        self.assertEqual(self.hammer.quantity_in_stock, 3)
        self.assertEqual(self.wrench.quantity_in_stock, 2)

        movements = list(order.stock_movements.order_by('pk'))
        self.assertEqual(len(movements), 2)
        self.assertEqual(movements[0].quantity, -2)
        self.assertEqual(
            movements[0].movement_type,
            StockMovement.MovementType.OUTGOING,
        )
        self.assertEqual(movements[0].sales_order, order)

    def test_dispatch_blocks_when_stock_is_insufficient(self):
        order = self.create_order([(self.hammer, 9)])

        response = self.client.post(
            reverse('sales_order_dispatch', args=[order.pk]),
            follow=True,
        )

        self.assertContains(response, 'Not enough stock for Hammer')

        order.refresh_from_db()
        self.hammer.refresh_from_db()

        self.assertEqual(order.status, SalesOrder.Status.PENDING)
        self.assertEqual(self.hammer.quantity_in_stock, 5)
        self.assertFalse(StockMovement.objects.exists())

    def test_dispatch_twice_is_a_no_op(self):
        order = self.create_order([(self.hammer, 1)])
        url = reverse('sales_order_dispatch', args=[order.pk])

        self.client.post(url)
        response = self.client.post(url, follow=True)

        self.assertContains(response, 'already been dispatched')

        self.hammer.refresh_from_db()
        self.assertEqual(self.hammer.quantity_in_stock, 4)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_dispatched_order_cannot_be_edited(self):
        order = self.create_order([(self.hammer, 1)], dispatch=True)

        response = self.client.get(
            reverse('sales_order_update', args=[order.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_update_to_direct_sale_dispatches_when_stock_is_available(self):
        order = self.create_order([(self.hammer, 2)])
        data = self.build_post_data([(self.hammer, '2')], is_direct=True)
        data['items-INITIAL_FORMS'] = '1'
        data['items-0-id'] = str(order.items.get().pk)

        response = self.client.post(
            reverse('sales_order_update', args=[order.pk]), data
        )

        self.assertRedirects(
            response,
            reverse('sales_order_detail', args=[order.pk]),
        )

        order.refresh_from_db()
        self.hammer.refresh_from_db()

        self.assertTrue(order.is_direct)
        self.assertEqual(order.status, SalesOrder.Status.DISPATCHED)
        self.assertEqual(self.hammer.quantity_in_stock, 3)

    def test_update_to_direct_sale_blocks_when_stock_is_missing(self):
        order = self.create_order([(self.hammer, 9)])
        data = self.build_post_data([(self.hammer, '9')], is_direct=True)
        data['items-INITIAL_FORMS'] = '1'
        data['items-0-id'] = str(order.items.get().pk)

        response = self.client.post(
            reverse('sales_order_update', args=[order.pk]), data
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This direct sale cannot be completed')
        self.assertNotContains(response, 'Continue anyway')

        order.refresh_from_db()
        self.hammer.refresh_from_db()

        self.assertFalse(order.is_direct)
        self.assertEqual(order.status, SalesOrder.Status.PENDING)
        self.assertEqual(self.hammer.quantity_in_stock, 5)

    def test_admin_can_delete_a_pending_order(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        order = self.create_order([(self.hammer, 1)])

        response = self.client.post(
            reverse('sales_order_delete', args=[order.pk])
        )

        self.assertRedirects(response, reverse('sales_order_list'))
        self.assertFalse(SalesOrder.objects.filter(pk=order.pk).exists())

    def test_staff_user_cannot_reach_the_delete_page(self):
        order = self.create_order([(self.hammer, 1)])

        response = self.client.get(
            reverse('sales_order_delete', args=[order.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_dispatched_order_cannot_be_deleted(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        order = self.create_order([(self.hammer, 1)], dispatch=True)

        response = self.client.get(
            reverse('sales_order_delete', args=[order.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(SalesOrder.objects.filter(pk=order.pk).exists())

    def test_detail_page_renders_items_and_movements(self):
        order = self.create_order([(self.hammer, 2)], dispatch=True)

        response = self.client.get(
            reverse('sales_order_detail', args=[order.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Retail')
        self.assertContains(response, 'Hammer')
        self.assertContains(response, 'Stock movements')
        self.assertContains(response, '-2')

    def test_ledger_links_to_the_sales_order(self):
        order = self.create_order([(self.hammer, 1)], dispatch=True)

        response = self.client.get(reverse('stock_movement_list'))

        self.assertContains(response, f'Sale #{order.pk}')
        self.assertContains(
            response,
            reverse('sales_order_detail', args=[order.pk]),
        )


class StockMovementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffer',
            password=PASSWORD,
            role=User.Role.STAFF,
        )
        self.category = Category.objects.create(name='Hardware')
        self.product = Product.objects.create(
            sku='SKU-1',
            name='Hammer',
            quantity_in_stock=10,
            reorder_level=2,
            category=self.category,
        )
        self.client.login(username='staffer', password=PASSWORD)

    def post_movement(self, movement_type, quantity, direction=''):
        return self.client.post(
            reverse('stock_movement_create'),
            {
                'product': self.product.pk,
                'movement_type': movement_type,
                'quantity': quantity,
                'direction': direction,
                'reference_note': '',
            },
        )

    def test_incoming_adds_stock(self):
        response = self.post_movement('incoming', '5')

        self.assertRedirects(response, reverse('stock_movement_list'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 15)

        movement = StockMovement.objects.get()
        self.assertEqual(movement.quantity, 5)
        self.assertEqual(movement.performed_by, self.staff)

    def test_outgoing_removes_stock(self):
        self.post_movement('outgoing', '4')

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 6)
        self.assertEqual(StockMovement.objects.get().quantity, -4)

    def test_adjustment_decrease_removes_stock(self):
        self.post_movement('adjustment', '3', direction='decrease')

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 7)
        self.assertEqual(StockMovement.objects.get().quantity, -3)

    def test_adjustment_increase_adds_stock(self):
        self.post_movement('adjustment', '2', direction='increase')

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 12)
        self.assertEqual(StockMovement.objects.get().quantity, 2)

    def test_adjustment_requires_a_direction(self):
        response = self.post_movement('adjustment', '3')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose whether stock goes up or down')
        self.assertFalse(StockMovement.objects.exists())

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 10)

    def test_outgoing_cannot_drop_stock_below_zero(self):
        response = self.post_movement('outgoing', '50')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Not enough stock')
        self.assertFalse(StockMovement.objects.exists())

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_in_stock, 10)

    def test_ledger_renders_signed_change(self):
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.staff,
            movement_type=StockMovement.MovementType.INCOMING,
            quantity=5,
        )
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.staff,
            movement_type=StockMovement.MovementType.OUTGOING,
            quantity=-2,
        )

        response = self.client.get(reverse('stock_movement_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hammer')
        self.assertContains(response, '+5')
        self.assertContains(response, '-2')

    def test_ledger_filters_by_type(self):
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.staff,
            movement_type=StockMovement.MovementType.INCOMING,
            quantity=5,
        )
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.staff,
            movement_type=StockMovement.MovementType.OUTGOING,
            quantity=-2,
        )

        response = self.client.get(reverse('stock_movement_list'), {'type': 'outgoing'})

        self.assertContains(response, '-2')
        self.assertNotContains(response, '+5')

    def test_ledger_search_filters_products(self):
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.staff,
            movement_type=StockMovement.MovementType.INCOMING,
            quantity=5,
        )

        response = self.client.get(reverse('stock_movement_list'), {'q': 'zzz'})

        self.assertNotContains(response, 'Hammer')

    def test_custom_movement_has_a_detail_link_in_the_reference_column(self):
        movement = StockMovement.record(
            product=self.product,
            quantity=5,
            movement_type=StockMovement.MovementType.INCOMING,
            user=self.staff,
            note='Opening count',
        )

        response = self.client.get(reverse('stock_movement_list'))

        self.assertContains(response, 'Opening count')
        self.assertContains(response, 'Detail')
        self.assertContains(
            response,
            reverse('stock_movement_detail', args=[movement.pk]),
        )

    def test_movement_detail_page_renders_the_entry(self):
        movement = StockMovement.record(
            product=self.product,
            quantity=-3,
            movement_type=StockMovement.MovementType.OUTGOING,
            user=self.staff,
            note='Damaged unit',
        )

        response = self.client.get(
            reverse('stock_movement_detail', args=[movement.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Movement #{movement.pk}')
        self.assertContains(response, 'Hammer')
        self.assertContains(response, '-3')
        self.assertContains(response, 'staffer')
        self.assertContains(response, 'Manual entry')
        self.assertContains(response, 'Damaged unit')

    def test_movement_detail_requires_login(self):
        movement = StockMovement.record(
            product=self.product,
            quantity=5,
            movement_type=StockMovement.MovementType.INCOMING,
            user=self.staff,
        )
        detail_url = reverse('stock_movement_detail', args=[movement.pk])
        self.client.logout()

        response = self.client.get(detail_url)

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={detail_url}",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(reverse('stock_movement_list'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('stock_movement_list')}",
        )


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
        detail = self.client.get(
            reverse('purchase_order_detail', args=[order.pk])
        )

        for heading in ('When', 'Product', 'Type', 'Change', 'By', 'Reference'):
            with self.subTest(column=heading):
                self.assertContains(ledger, f'>{heading}</th>')
                self.assertContains(detail, f'>{heading}</th>')

    def test_pricing_is_out_of_scope(self):
        product_page = self.client.get(reverse('product_list'))
        form_page = self.client.get(reverse('product_create'))

        self.assertNotContains(product_page, 'Unit price')
        self.assertNotContains(form_page, 'unit_price')

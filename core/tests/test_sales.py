from django.test import TestCase
from django.urls import reverse

from core.models import (
    Category,
    Customer,
    Product,
    SalesOrder,
    SalesOrderItem,
    StockMovement,
)
from core.tests.helpers import PASSWORD, User


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

        response = self.client.post(reverse('sales_order_create'), data, follow=True)

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

        response = self.client.post(reverse('sales_order_dispatch', args=[order.pk]))

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

        response = self.client.get(reverse('sales_order_update', args=[order.pk]))

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

        response = self.client.post(reverse('sales_order_delete', args=[order.pk]))

        self.assertRedirects(response, reverse('sales_order_list'))
        self.assertFalse(SalesOrder.objects.filter(pk=order.pk).exists())

    def test_staff_user_cannot_reach_the_delete_page(self):
        order = self.create_order([(self.hammer, 1)])

        response = self.client.get(reverse('sales_order_delete', args=[order.pk]))

        self.assertEqual(response.status_code, 403)

    def test_dispatched_order_cannot_be_deleted(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        order = self.create_order([(self.hammer, 1)], dispatch=True)

        response = self.client.get(reverse('sales_order_delete', args=[order.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(SalesOrder.objects.filter(pk=order.pk).exists())

    def test_detail_page_renders_items_and_movements(self):
        order = self.create_order([(self.hammer, 2)], dispatch=True)

        response = self.client.get(reverse('sales_order_detail', args=[order.pk]))

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

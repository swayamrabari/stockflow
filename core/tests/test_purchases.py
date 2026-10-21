from django.test import TestCase
from django.urls import reverse

from core.models import (
    Category,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)
from core.tests.helpers import PASSWORD, User


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
            f'{reverse("login")}?next={reverse("purchase_order_list")}',
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

        response = self.client.get(reverse('purchase_order_list'), {'q': str(order.pk)})

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

        response = self.client.get(reverse('purchase_order_detail', args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Supplies')
        self.assertContains(response, 'Hammer')

    def test_update_page_renders_existing_items(self):
        order = self.create_order([(self.hammer, 2)])

        response = self.client.get(reverse('purchase_order_update', args=[order.pk]))

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

        response = self.client.get(reverse('purchase_order_update', args=[order.pk]))

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

        response = self.client.post(reverse('purchase_order_delete', args=[order.pk]))

        self.assertRedirects(response, reverse('purchase_order_list'))
        self.assertFalse(PurchaseOrder.objects.filter(pk=order.pk).exists())

    def test_staff_user_cannot_reach_the_delete_page(self):
        order = self.create_order([(self.hammer, 1)])

        response = self.client.get(reverse('purchase_order_delete', args=[order.pk]))

        self.assertEqual(response.status_code, 403)

    def test_received_order_cannot_be_deleted(self):
        User.objects.create_user(
            username='adminny',
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client.login(username='adminny', password=PASSWORD)

        order = self.create_order([(self.hammer, 1)], receive=True)

        response = self.client.get(reverse('purchase_order_delete', args=[order.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PurchaseOrder.objects.filter(pk=order.pk).exists())

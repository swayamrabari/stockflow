from django.test import TestCase
from django.urls import reverse

from core.models import Category, Product, StockMovement
from core.tests.helpers import PASSWORD, User


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

        response = self.client.get(reverse('stock_movement_detail', args=[movement.pk]))

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
            f'{reverse("login")}?next={detail_url}',
        )

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(reverse('stock_movement_list'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("stock_movement_list")}',
        )

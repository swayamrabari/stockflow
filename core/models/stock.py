from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models.catalog import Product
from core.models.purchases import PurchaseOrder
from core.models.sales import SalesOrder


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        INCOMING = 'incoming', 'Incoming'
        OUTGOING = 'outgoing', 'Outgoing'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_movements',
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_movements',
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
    )

    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
    )

    quantity = models.IntegerField(
        help_text='Signed change: positive adds stock, negative removes it.',
    )
    reference_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'stock_movements'
        ordering = ('-created_at',)
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=~Q(quantity=0),
                name='stock_movement_quantity_nonzero',
            ),
        ]

    def __str__(self):
        return f'{self.product.sku} {self.signed_quantity}'

    @property
    def signed_quantity(self):
        """Render as +3 / -2 in templates."""
        return f'{self.quantity:+d}'

    @classmethod
    def record(
        cls,
        *,
        product,
        quantity,
        movement_type,
        user,
        note='',
        purchase_order=None,
        sales_order=None,
    ):
        """Create a movement and apply it to the product's stock.

        This is the only place stock and the ledger change together, so
        the two can never drift apart.
        """
        if quantity == 0:
            raise ValidationError('Quantity cannot be zero.')

        if movement_type == cls.MovementType.INCOMING and quantity < 0:
            raise ValidationError('Incoming movements must be positive.')

        if movement_type == cls.MovementType.OUTGOING and quantity > 0:
            raise ValidationError('Outgoing movements must be negative.')

        if product.quantity_in_stock + quantity < 0:
            raise ValidationError('Not enough stock for this movement.')

        movement = cls.objects.create(
            product=product,
            performed_by=user,
            movement_type=movement_type,
            quantity=quantity,
            reference_note=note,
            purchase_order=purchase_order,
            sales_order=sales_order,
        )

        product.quantity_in_stock += quantity
        product.save(update_fields=['quantity_in_stock', 'updated_at'])

        return movement

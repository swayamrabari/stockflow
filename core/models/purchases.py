from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models.catalog import Product
from core.models.partners import Supplier


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RECEIVED = 'received', 'Received'

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_purchase_orders',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    is_direct = models.BooleanField(
        default=False,
        verbose_name='Direct / local order',
        help_text=(
            'Goods are already on hand, so the order is received '
            'immediately and added to stock.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'purchase_orders'
        ordering = ('-created_at',)

    def __str__(self):
        return f'Purchase #{self.pk} ({self.status})'

    def receive(self, user):
        """Mark the order received and push its quantities into stock.

        Each line writes one incoming StockMovement, so the order stays
        traceable from the inventory ledger.
        """
        from core.models.stock import StockMovement

        if self.status == self.Status.RECEIVED:
            return

        for item in self.items.select_related('product'):
            StockMovement.record(
                product=item.product,
                quantity=item.quantity,
                movement_type=StockMovement.MovementType.INCOMING,
                user=user,
                note=f'Purchase #{self.pk}',
                purchase_order=self,
            )

        self.status = self.Status.RECEIVED
        self.received_at = timezone.now()
        self.save(update_fields=['status', 'received_at'])


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items',
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='purchase_order_items',
    )

    quantity = models.IntegerField()

    class Meta:
        db_table = 'purchase_order_items'
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name='po_item_quantity_positive',
            ),
        ]

    def __str__(self):
        return f'PO #{self.purchase_order_id} - {self.product.name} x {self.quantity}'

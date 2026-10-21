from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from core.models.catalog import Product
from core.models.partners import Customer


class SalesOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DISPATCHED = 'dispatched', 'Dispatched'

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='sales_orders',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_sales_orders',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    is_direct = models.BooleanField(
        default=False,
        verbose_name='Direct / local sale',
        help_text=(
            'Goods are handed over immediately, so the sale is dispatched '
            'at creation and removed from stock.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sales_orders'
        ordering = ('-created_at',)

    def __str__(self):
        return f'Sale #{self.pk} ({self.status})'

    @property
    def has_enough_stock(self):
        """True when every line can be covered from current stock."""
        return all(
            item.quantity <= item.product.quantity_in_stock for item in self.items.all()
        )

    def dispatch(self, user):
        """Mark the order dispatched and remove its quantities from stock.

        Stock is checked and locked inside one transaction, so two people
        dispatching at once cannot promise the same units.
        """
        from core.models.stock import StockMovement

        if self.status == self.Status.DISPATCHED:
            return

        items = list(self.items.select_related('product'))

        with transaction.atomic():
            products = {
                product.pk: product
                for product in Product.objects.select_for_update().filter(
                    pk__in=[item.product_id for item in items]
                )
            }

            for item in items:
                product = products[item.product_id]

                if item.quantity > product.quantity_in_stock:
                    raise ValidationError(
                        f'Not enough stock for {product.name}: only '
                        f'{product.quantity_in_stock} available.'
                    )

            for item in items:
                StockMovement.record(
                    product=products[item.product_id],
                    quantity=-item.quantity,
                    movement_type=StockMovement.MovementType.OUTGOING,
                    user=user,
                    note=f'Sale #{self.pk}',
                    sales_order=self,
                )

            self.status = self.Status.DISPATCHED
            self.dispatched_at = timezone.now()
            self.save(update_fields=['status', 'dispatched_at'])


class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='items',
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sales_order_items',
    )

    quantity = models.IntegerField()

    class Meta:
        db_table = 'sales_order_items'
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name='so_item_quantity_positive',
            ),
        ]

    def __str__(self):
        return f'SO #{self.sales_order_id} - {self.product.name} x {self.quantity}'

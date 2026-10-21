from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        STAFF = 'staff', 'Staff'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.username

    @property
    def is_admin(self):
        """Single source of truth for the admin role rule."""
        return self.is_authenticated and (
            self.role == self.Role.ADMIN or self.is_superuser
        )


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'

        ordering = ('name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    quantity_in_stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ('name',)
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(quantity_in_stock__gte=0),
                name='product_stock_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(reorder_level__gte=0),
                name='product_reorder_nonnegative',
            ),
        ]

    def __str__(self):
        return f'{self.sku} - {self.name}'


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customers'
        ordering = ('name',)

    def __str__(self):
        return self.name


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
            item.quantity <= item.product.quantity_in_stock
            for item in self.items.all()
        )

    def dispatch(self, user):
        """Mark the order dispatched and remove its quantities from stock.

        Stock is checked and locked inside one transaction, so two people
        dispatching at once cannot promise the same units.
        """
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

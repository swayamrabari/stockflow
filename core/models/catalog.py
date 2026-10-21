from django.db import models
from django.db.models import Q


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

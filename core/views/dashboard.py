from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.views.generic import TemplateView

from core.models import (
    Category,
    Customer,
    Product,
    PurchaseOrder,
    SalesOrder,
    StockMovement,
    Supplier,
)
from core.permissions import AdminRequiredMixin


class DashboardView(AdminRequiredMixin, TemplateView):
    """Admin-only, single-page snapshot of the whole inventory."""

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        product_stats = Product.objects.aggregate(
            total=Count('id'),
            units=Coalesce(Sum('quantity_in_stock'), 0),
            low_stock=Count(
                'id',
                filter=Q(quantity_in_stock__lte=F('reorder_level')),
            ),
            out_of_stock=Count('id', filter=Q(quantity_in_stock=0)),
        )

        purchase_stats = PurchaseOrder.objects.filter(
            status=PurchaseOrder.Status.PENDING
        ).aggregate(
            count=Count('id', distinct=True),
            units=Coalesce(Sum('items__quantity'), 0),
        )

        sales_stats = SalesOrder.objects.filter(
            status=SalesOrder.Status.PENDING
        ).aggregate(
            count=Count('id', distinct=True),
            units=Coalesce(Sum('items__quantity'), 0),
        )

        low_stock_products = (
            Product.objects.select_related('category')
            .filter(quantity_in_stock__lte=F('reorder_level'))
            .order_by('quantity_in_stock', 'name')[:6]
        )

        recent_purchases = (
            PurchaseOrder.objects.select_related('supplier', 'created_by')
            .prefetch_related('items')
            .order_by('-created_at')[:5]
        )

        recent_sales = (
            SalesOrder.objects.select_related('customer', 'created_by')
            .prefetch_related('items__product')
            .order_by('-created_at')[:5]
        )

        recent_movements = StockMovement.objects.select_related(
            'product',
            'performed_by',
            'purchase_order',
            'sales_order',
        ).order_by('-created_at')[:8]

        context.update(
            {
                'product_count': product_stats['total'],
                'total_units': product_stats['units'],
                'low_stock_count': product_stats['low_stock'],
                'out_of_stock_count': product_stats['out_of_stock'],
                'category_count': Category.objects.count(),
                'supplier_count': Supplier.objects.count(),
                'customer_count': Customer.objects.count(),
                'pending_purchase_count': purchase_stats['count'],
                'pending_purchase_units': purchase_stats['units'],
                'pending_sales_count': sales_stats['count'],
                'pending_sales_units': sales_stats['units'],
                'low_stock_products': low_stock_products,
                'recent_purchases': recent_purchases,
                'recent_sales': recent_sales,
                'recent_movements': recent_movements,
            }
        )

        return context

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from core.forms import (
    CategoryForm,
    CustomerForm,
    ProductForm,
    PurchaseOrderForm,
    PurchaseOrderItemFormSet,
    RegistrationForm,
    SalesOrderForm,
    SalesOrderItemFormSet,
    StockMovementForm,
    SupplierForm,
)
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


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class HomeRedirectView(LoginRequiredMixin, View):
    """Send each role to the right landing page after login."""

    def get(self, request):
        if request.user.is_admin:
            return redirect('dashboard')
        return redirect('product_list')


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

        recent_movements = (
            StockMovement.objects.select_related(
                'product',
                'performed_by',
                'purchase_order',
                'sales_order',
            ).order_by('-created_at')[:8]
        )

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


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'category_form.html'
    success_url = reverse_lazy('category_list')


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'category_form.html'
    success_url = reverse_lazy('category_list')


class CategoryDeleteView(AdminRequiredMixin, DeleteView):
    model = Category
    template_name = 'category_confirm_delete.html'
    success_url = reverse_lazy('category_list')


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'

    def get_queryset(self):
        queryset = Product.objects.select_related('category')

        search = self.request.GET.get('q', '').strip()
        category_id = self.request.GET.get('category', '').strip()
        stock = self.request.GET.get('stock', '').strip()

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(sku__icontains=search)
            )

        if category_id.isdigit():
            queryset = queryset.filter(category_id=int(category_id))

        if stock == 'low':
            queryset = queryset.filter(
                quantity_in_stock__lte=F('reorder_level')
            )
        elif stock == 'out':
            queryset = queryset.filter(quantity_in_stock=0)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['categories'] = Category.objects.order_by('name')
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_stock'] = self.request.GET.get('stock', '')

        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'product_form.html'
    success_url = reverse_lazy('product_list')


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'product_form.html'
    success_url = reverse_lazy('product_list')


class ProductDeleteView(AdminRequiredMixin, DeleteView):
    model = Product
    template_name = 'product_confirm_delete.html'
    success_url = reverse_lazy('product_list')


class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'supplier_list.html'
    context_object_name = 'suppliers'


class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'supplier_form.html'
    success_url = reverse_lazy('supplier_list')


class SupplierUpdateView(LoginRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'supplier_form.html'
    success_url = reverse_lazy('supplier_list')


class SupplierDeleteView(AdminRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'supplier_confirm_delete.html'
    success_url = reverse_lazy('supplier_list')


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'customer_list.html'
    context_object_name = 'customers'


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customer_form.html'
    success_url = reverse_lazy('customer_list')


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customer_form.html'
    success_url = reverse_lazy('customer_list')


class CustomerDeleteView(AdminRequiredMixin, DeleteView):
    model = Customer
    template_name = 'customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')


class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchase_order_list.html'
    context_object_name = 'purchase_orders'

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related(
            'supplier', 'created_by'
        ).prefetch_related('items')

        search = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if search:
            filters = Q(supplier__name__icontains=search)

            if search.isdigit():
                filters |= Q(pk=int(search))

            queryset = queryset.filter(filters)

        if status in PurchaseOrder.Status.values:
            queryset = queryset.filter(status=status)

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['statuses'] = PurchaseOrder.Status.choices
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')

        return context


class PurchaseOrderFormMixin:
    """Shared line-item formset for PO forms."""

    def get_items_formset(self):
        return PurchaseOrderItemFormSet(
            self.request.POST if self.request.method == 'POST' else None,
            instance=self.object,
            prefix='items',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if 'items' not in context:
            context['items'] = self.get_items_formset()

        return context


class PurchaseOrderCreateView(
    LoginRequiredMixin, PurchaseOrderFormMixin, CreateView
):
    """Create a purchase and its line items from a single form.

    The supplier lives in ``PurchaseOrderForm``; the line items are a
    Django inline formset, so one POST writes the header and every row
    inside the same transaction.
    """

    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase_order_form.html'
    success_url = reverse_lazy('purchase_order_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user

        items = self.get_items_formset()

        if not items.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, items=items)
            )

        with transaction.atomic():
            self.object.save()
            items.save()

            if self.object.is_direct:
                self.object.receive(self.request.user)

        if self.object.is_direct:
            messages.success(
                self.request,
                f'Purchase #{self.object.pk} created and received '
                'into stock.',
            )
        else:
            messages.success(
                self.request,
                f'Purchase #{self.object.pk} created.',
            )

        return redirect(self.get_success_url())


class PurchaseOrderUpdateView(
    LoginRequiredMixin, PurchaseOrderFormMixin, UpdateView
):
    """Edit a pending purchase and its line items.

    Received orders are filtered out (404) because their quantities have
    already been applied to stock.
    """

    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase_order_form.html'

    def get_queryset(self):
        return PurchaseOrder.objects.filter(status=PurchaseOrder.Status.PENDING)

    def form_valid(self, form):
        items = self.get_items_formset()

        if not items.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, items=items)
            )

        with transaction.atomic():
            self.object = form.save()
            items.save()

            if self.object.is_direct:
                self.object.receive(self.request.user)

        messages.success(
            self.request,
            f'Purchase #{self.object.pk} updated.',
        )

        return redirect('purchase_order_detail', pk=self.object.pk)


class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchase_order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return PurchaseOrder.objects.select_related(
            'supplier', 'created_by'
        ).prefetch_related('items__product', 'stock_movements__product')


class PurchaseOrderReceiveView(LoginRequiredMixin, View):
    """POST-only action: receive a pending order into stock."""

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)

        if order.status == PurchaseOrder.Status.RECEIVED:
            messages.info(
                request,
                f'Purchase #{order.pk} has already been received.',
            )
        else:
            with transaction.atomic():
                order.receive(request.user)

            messages.success(
                request,
                f'Purchase #{order.pk} received into stock.',
            )

        return redirect('purchase_order_detail', pk=order.pk)


class PurchaseOrderDeleteView(AdminRequiredMixin, DeleteView):
    model = PurchaseOrder
    template_name = 'purchase_order_confirm_delete.html'
    success_url = reverse_lazy('purchase_order_list')

    def get_queryset(self):
        # Received orders are part of the stock ledger, so they stay put.
        return PurchaseOrder.objects.filter(status=PurchaseOrder.Status.PENDING)


class SalesOrderListView(LoginRequiredMixin, ListView):
    model = SalesOrder
    template_name = 'sales_order_list.html'
    context_object_name = 'sales_orders'

    def get_queryset(self):
        queryset = SalesOrder.objects.select_related(
            'customer', 'created_by'
        ).prefetch_related('items__product')

        search = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if search:
            filters = Q(customer__name__icontains=search)

            if search.isdigit():
                filters |= Q(pk=int(search))

            queryset = queryset.filter(filters)

        if status in SalesOrder.Status.values:
            queryset = queryset.filter(status=status)

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['statuses'] = SalesOrder.Status.choices
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')

        return context


class SalesOrderFormMixin:
    """Shared line-item formset for sale forms."""

    def get_items_formset(self):
        return SalesOrderItemFormSet(
            self.request.POST if self.request.method == 'POST' else None,
            instance=self.object,
            prefix='items',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if 'items' not in context:
            context['items'] = self.get_items_formset()

        return context

    def get_shortages(self, items):
        """Return (product, requested, available) rows that exceed stock."""
        shortages = []

        for item_form in items.forms:
            if not item_form.cleaned_data:
                continue

            if item_form.cleaned_data.get('DELETE'):
                continue

            product = item_form.cleaned_data.get('product')
            quantity = item_form.cleaned_data.get('quantity')

            if product and quantity and quantity > product.quantity_in_stock:
                shortages.append(
                    (product, quantity, product.quantity_in_stock)
                )

        return shortages


class SalesOrderCreateView(LoginRequiredMixin, SalesOrderFormMixin, CreateView):
    """Create a sale and its line items from a single form."""

    model = SalesOrder
    form_class = SalesOrderForm
    template_name = 'sales_order_form.html'
    success_url = reverse_lazy('sales_order_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user

        items = self.get_items_formset()

        if not items.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, items=items)
            )

        shortages = self.get_shortages(items)
        requested_direct = form.cleaned_data.get('is_direct')

        # A direct sale is handed over immediately, so it can never be saved
        # without enough stock - not even with an explicit confirmation.
        if requested_direct and shortages:
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    items=items,
                    shortages=shortages,
                    direct_error=True,
                )
            )

        if shortages and self.request.POST.get('confirm') != '1':
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    items=items,
                    shortages=shortages,
                )
            )

        dispatched_directly = bool(requested_direct)

        try:
            with transaction.atomic():
                self.object.save()
                items.save()

                if dispatched_directly:
                    self.object.dispatch(self.request.user)
        except ValidationError as error:
            # Stock moved between the check and the dispatch. Nothing was
            # saved, so show the error and let the user fix the quantities.
            self.object = None

            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    items=items,
                    direct_error=' '.join(error.messages),
                )
            )

        if dispatched_directly:
            messages.success(
                self.request,
                f'Sale #{self.object.pk} created and dispatched.',
            )
        else:
            messages.success(
                self.request,
                f'Sale #{self.object.pk} created.',
            )

        return redirect(self.get_success_url())


class SalesOrderUpdateView(LoginRequiredMixin, SalesOrderFormMixin, UpdateView):
    """Edit a pending sale and its line items."""

    model = SalesOrder
    form_class = SalesOrderForm
    template_name = 'sales_order_form.html'

    def get_queryset(self):
        return SalesOrder.objects.filter(status=SalesOrder.Status.PENDING)

    def form_valid(self, form):
        items = self.get_items_formset()

        if not items.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, items=items)
            )

        shortages = self.get_shortages(items)
        requested_direct = form.cleaned_data.get('is_direct')

        if requested_direct and shortages:
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    items=items,
                    shortages=shortages,
                    direct_error=True,
                )
            )

        if shortages and self.request.POST.get('confirm') != '1':
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    items=items,
                    shortages=shortages,
                )
            )

        dispatched_directly = bool(requested_direct)

        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.save()
                items.save()

                if dispatched_directly:
                    self.object.dispatch(self.request.user)
        except ValidationError as error:
            # Stock moved between the check and the dispatch. Nothing was
            # saved, so show the error and let the user fix the quantities.
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    items=items,
                    direct_error=' '.join(error.messages),
                )
            )

        if dispatched_directly:
            messages.success(
                self.request,
                f'Sale #{self.object.pk} updated and dispatched out of stock.',
            )
        else:
            messages.success(
                self.request,
                f'Sale #{self.object.pk} updated.',
            )

        return redirect('sales_order_detail', pk=self.object.pk)


class SalesOrderDetailView(LoginRequiredMixin, DetailView):
    model = SalesOrder
    template_name = 'sales_order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return SalesOrder.objects.select_related(
            'customer', 'created_by'
        ).prefetch_related('items__product', 'stock_movements__product')


class SalesOrderDispatchView(LoginRequiredMixin, View):
    """POST-only action: dispatch a pending order out of stock."""

    def post(self, request, pk):
        order = get_object_or_404(SalesOrder, pk=pk)

        if order.status == SalesOrder.Status.DISPATCHED:
            messages.info(
                request,
                f'Sale #{order.pk} has already been dispatched.',
            )
        else:
            try:
                order.dispatch(request.user)
            except ValidationError as error:
                messages.error(request, ' '.join(error.messages))
            else:
                messages.success(
                    request,
                    f'Sale #{order.pk} dispatched and removed from '
                    'stock.',
                )

        return redirect('sales_order_detail', pk=order.pk)


class SalesOrderDeleteView(AdminRequiredMixin, DeleteView):
    model = SalesOrder
    template_name = 'sales_order_confirm_delete.html'
    success_url = reverse_lazy('sales_order_list')

    def get_queryset(self):
        # Dispatched orders are part of the stock ledger, so they stay put.
        return SalesOrder.objects.filter(status=SalesOrder.Status.PENDING)


class StockMovementListView(LoginRequiredMixin, ListView):
    model = StockMovement
    template_name = 'stock_movement_list.html'
    context_object_name = 'movements'
    paginate_by = 25

    def get_queryset(self):
        queryset = StockMovement.objects.select_related(
            'product', 'performed_by', 'purchase_order', 'sales_order'
        )

        search = self.request.GET.get('q', '').strip()
        movement_type = self.request.GET.get('type', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search)
                | Q(product__sku__icontains=search)
            )

        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['movement_types'] = StockMovement.MovementType.choices
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_type'] = self.request.GET.get('type', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')

        return context


class StockMovementDetailView(LoginRequiredMixin, DetailView):
    model = StockMovement
    template_name = 'stock_movement_detail.html'
    context_object_name = 'movement'

    def get_queryset(self):
        return StockMovement.objects.select_related(
            'product', 'performed_by', 'purchase_order', 'sales_order'
        )


class StockMovementCreateView(LoginRequiredMixin, FormView):
    form_class = StockMovementForm
    template_name = 'stock_movement_form.html'
    success_url = reverse_lazy('stock_movement_list')

    def form_valid(self, form):
        with transaction.atomic():
            form.save(self.request.user)

        messages.success(self.request, 'Stock movement recorded.')

        return super().form_valid(form)

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from core.forms import SalesOrderForm, SalesOrderItemFormSet
from core.models import SalesOrder
from core.permissions import AdminRequiredMixin


class SalesOrderListView(LoginRequiredMixin, ListView):
    model = SalesOrder
    template_name = 'sales/list.html'
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
                shortages.append((product, quantity, product.quantity_in_stock))

        return shortages


class SalesOrderCreateView(LoginRequiredMixin, SalesOrderFormMixin, CreateView):
    """Create a sale and its line items from a single form."""

    model = SalesOrder
    form_class = SalesOrderForm
    template_name = 'sales/form.html'
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
    template_name = 'sales/form.html'

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
    template_name = 'sales/detail.html'
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
                    f'Sale #{order.pk} dispatched and removed from stock.',
                )

        return redirect('sales_order_detail', pk=order.pk)


class SalesOrderDeleteView(AdminRequiredMixin, DeleteView):
    model = SalesOrder
    template_name = 'sales/confirm_delete.html'
    success_url = reverse_lazy('sales_order_list')

    def get_queryset(self):
        return SalesOrder.objects.filter(status=SalesOrder.Status.PENDING)

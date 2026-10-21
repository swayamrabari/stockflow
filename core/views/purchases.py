from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
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

from core.forms import PurchaseOrderForm, PurchaseOrderItemFormSet
from core.models import PurchaseOrder
from core.permissions import AdminRequiredMixin


class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchases/list.html'
    context_object_name = 'purchase_orders'
    paginate_by = 20

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


class PurchaseOrderCreateView(LoginRequiredMixin, PurchaseOrderFormMixin, CreateView):
    """Create a purchase and its line items from a single form."""

    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchases/form.html'
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
                f'Purchase #{self.object.pk} created and received into stock.',
            )
        else:
            messages.success(
                self.request,
                f'Purchase #{self.object.pk} created.',
            )

        return redirect(self.get_success_url())


class PurchaseOrderUpdateView(LoginRequiredMixin, PurchaseOrderFormMixin, UpdateView):
    """Edit a pending purchase and its line items."""

    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchases/form.html'

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
    template_name = 'purchases/detail.html'
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
    template_name = 'purchases/confirm_delete.html'
    success_url = reverse_lazy('purchase_order_list')

    def get_queryset(self):
        return PurchaseOrder.objects.filter(status=PurchaseOrder.Status.PENDING)

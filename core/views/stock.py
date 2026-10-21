from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from core.forms import StockMovementForm
from core.models import StockMovement


class StockMovementListView(LoginRequiredMixin, ListView):
    model = StockMovement
    template_name = 'stock/list.html'
    context_object_name = 'movements'
    paginate_by = 20

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
                Q(product__name__icontains=search) | Q(product__sku__icontains=search)
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
    template_name = 'stock/detail.html'
    context_object_name = 'movement'

    def get_queryset(self):
        return StockMovement.objects.select_related(
            'product', 'performed_by', 'purchase_order', 'sales_order'
        )


class StockMovementCreateView(LoginRequiredMixin, FormView):
    form_class = StockMovementForm
    template_name = 'stock/form.html'
    success_url = reverse_lazy('stock_movement_list')

    def form_valid(self, form):
        with transaction.atomic():
            form.save(self.request.user)

        messages.success(self.request, 'Stock movement recorded.')

        return super().form_valid(form)

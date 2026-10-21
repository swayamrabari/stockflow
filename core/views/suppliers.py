from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.forms import SupplierForm
from core.models import Supplier
from core.permissions import AdminRequiredMixin


class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/list.html'
    context_object_name = 'suppliers'
    paginate_by = 20


class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/form.html'
    success_url = reverse_lazy('supplier_list')


class SupplierUpdateView(LoginRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/form.html'
    success_url = reverse_lazy('supplier_list')


class SupplierDeleteView(AdminRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'suppliers/confirm_delete.html'
    success_url = reverse_lazy('supplier_list')

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.forms import CustomerForm
from core.models import Customer
from core.permissions import AdminRequiredMixin


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'customers/list.html'
    context_object_name = 'customers'
    paginate_by = 20


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/form.html'
    success_url = reverse_lazy('customer_list')


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/form.html'
    success_url = reverse_lazy('customer_list')


class CustomerDeleteView(AdminRequiredMixin, DeleteView):
    model = Customer
    template_name = 'customers/confirm_delete.html'
    success_url = reverse_lazy('customer_list')

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.forms import CategoryForm
from core.models import Category
from core.permissions import AdminRequiredMixin


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'categories/list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'categories/form.html'
    success_url = reverse_lazy('category_list')


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'categories/form.html'
    success_url = reverse_lazy('category_list')


class CategoryDeleteView(AdminRequiredMixin, DeleteView):
    model = Category
    template_name = 'categories/confirm_delete.html'
    success_url = reverse_lazy('category_list')

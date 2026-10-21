from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core.forms import ProductForm
from core.models import Category, Product
from core.permissions import AdminRequiredMixin


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 20

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
            queryset = queryset.filter(quantity_in_stock__lte=F('reorder_level'))
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
    template_name = 'products/form.html'
    success_url = reverse_lazy('product_list')


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'products/form.html'
    success_url = reverse_lazy('product_list')


class ProductDeleteView(AdminRequiredMixin, DeleteView):
    model = Product
    template_name = 'products/confirm_delete.html'
    success_url = reverse_lazy('product_list')

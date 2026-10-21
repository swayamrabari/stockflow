from django.urls import path

from core.views.suppliers import (
    SupplierCreateView,
    SupplierDeleteView,
    SupplierListView,
    SupplierUpdateView,
)

urlpatterns = [
    path('', SupplierListView.as_view(), name='supplier_list'),
    path('create/', SupplierCreateView.as_view(), name='supplier_create'),
    path('<int:pk>/update/', SupplierUpdateView.as_view(), name='supplier_update'),
    path('<int:pk>/delete/', SupplierDeleteView.as_view(), name='supplier_delete'),
]

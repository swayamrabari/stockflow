from django.urls import path

from core.views.customers import (
    CustomerCreateView,
    CustomerDeleteView,
    CustomerListView,
    CustomerUpdateView,
)

urlpatterns = [
    path('', CustomerListView.as_view(), name='customer_list'),
    path('create/', CustomerCreateView.as_view(), name='customer_create'),
    path('<int:pk>/update/', CustomerUpdateView.as_view(), name='customer_update'),
    path('<int:pk>/delete/', CustomerDeleteView.as_view(), name='customer_delete'),
]

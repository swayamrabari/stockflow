from django.urls import path

from core.views.sales import (
    SalesOrderCreateView,
    SalesOrderDeleteView,
    SalesOrderDetailView,
    SalesOrderDispatchView,
    SalesOrderListView,
    SalesOrderUpdateView,
)

urlpatterns = [
    path('', SalesOrderListView.as_view(), name='sales_order_list'),
    path('create/', SalesOrderCreateView.as_view(), name='sales_order_create'),
    path('<int:pk>/', SalesOrderDetailView.as_view(), name='sales_order_detail'),
    path('<int:pk>/update/', SalesOrderUpdateView.as_view(), name='sales_order_update'),
    path(
        '<int:pk>/dispatch/',
        SalesOrderDispatchView.as_view(),
        name='sales_order_dispatch',
    ),
    path('<int:pk>/delete/', SalesOrderDeleteView.as_view(), name='sales_order_delete'),
]

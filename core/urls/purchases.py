from django.urls import path

from core.views.purchases import (
    PurchaseOrderCreateView,
    PurchaseOrderDeleteView,
    PurchaseOrderDetailView,
    PurchaseOrderListView,
    PurchaseOrderReceiveView,
    PurchaseOrderUpdateView,
)

urlpatterns = [
    path('', PurchaseOrderListView.as_view(), name='purchase_order_list'),
    path('create/', PurchaseOrderCreateView.as_view(), name='purchase_order_create'),
    path('<int:pk>/', PurchaseOrderDetailView.as_view(), name='purchase_order_detail'),
    path(
        '<int:pk>/update/',
        PurchaseOrderUpdateView.as_view(),
        name='purchase_order_update',
    ),
    path(
        '<int:pk>/receive/',
        PurchaseOrderReceiveView.as_view(),
        name='purchase_order_receive',
    ),
    path(
        '<int:pk>/delete/',
        PurchaseOrderDeleteView.as_view(),
        name='purchase_order_delete',
    ),
]

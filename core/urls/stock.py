from django.urls import path

from core.views.stock import (
    StockMovementCreateView,
    StockMovementDetailView,
    StockMovementListView,
)

urlpatterns = [
    path('', StockMovementListView.as_view(), name='stock_movement_list'),
    path('create/', StockMovementCreateView.as_view(), name='stock_movement_create'),
    path('<int:pk>/', StockMovementDetailView.as_view(), name='stock_movement_detail'),
]

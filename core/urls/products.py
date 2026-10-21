from django.urls import path

from core.views.products import (
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
)

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('create/', ProductCreateView.as_view(), name='product_create'),
    path('<int:pk>/update/', ProductUpdateView.as_view(), name='product_update'),
    path('<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
]

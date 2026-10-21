from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from core.forms import LoginForm
from core.views import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    CustomerCreateView,
    CustomerDeleteView,
    CustomerListView,
    CustomerUpdateView,
    DashboardView,
    HomeRedirectView,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
    PurchaseOrderCreateView,
    PurchaseOrderDeleteView,
    PurchaseOrderDetailView,
    PurchaseOrderListView,
    PurchaseOrderReceiveView,
    PurchaseOrderUpdateView,
    RegisterView,
    SalesOrderCreateView,
    SalesOrderDeleteView,
    SalesOrderDetailView,
    SalesOrderDispatchView,
    SalesOrderListView,
    SalesOrderUpdateView,
    StockMovementCreateView,
    StockMovementDetailView,
    StockMovementListView,
    SupplierCreateView,
    SupplierDeleteView,
    SupplierListView,
    SupplierUpdateView,
)

urlpatterns = [
    path('', HomeRedirectView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('register/', RegisterView.as_view(), name='register'),
    path(
        'login/',
        LoginView.as_view(authentication_form=LoginForm),
        name='login',
    ),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categories/create/', CategoryCreateView.as_view(), name='category_create'),
    path(
        'categories/<int:pk>/update/',
        CategoryUpdateView.as_view(),
        name='category_update',
    ),
    path(
        'categories/<int:pk>/delete/',
        CategoryDeleteView.as_view(),
        name='category_delete',
    ),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'),
    path(
        'products/<int:pk>/update/', ProductUpdateView.as_view(), name='product_update'
    ),
    path(
        'products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'
    ),
    path('suppliers/', SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/create/', SupplierCreateView.as_view(), name='supplier_create'),
    path(
        'suppliers/<int:pk>/update/',
        SupplierUpdateView.as_view(),
        name='supplier_update',
    ),
    path(
        'suppliers/<int:pk>/delete/',
        SupplierDeleteView.as_view(),
        name='supplier_delete',
    ),
    path('customers/', CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', CustomerCreateView.as_view(), name='customer_create'),
    path(
        'customers/<int:pk>/update/',
        CustomerUpdateView.as_view(),
        name='customer_update',
    ),
    path(
        'customers/<int:pk>/delete/',
        CustomerDeleteView.as_view(),
        name='customer_delete',
    ),
    path(
        'purchase-orders/',
        PurchaseOrderListView.as_view(),
        name='purchase_order_list',
    ),
    path(
        'purchase-orders/create/',
        PurchaseOrderCreateView.as_view(),
        name='purchase_order_create',
    ),
    path(
        'purchase-orders/<int:pk>/',
        PurchaseOrderDetailView.as_view(),
        name='purchase_order_detail',
    ),
    path(
        'purchase-orders/<int:pk>/update/',
        PurchaseOrderUpdateView.as_view(),
        name='purchase_order_update',
    ),
    path(
        'purchase-orders/<int:pk>/receive/',
        PurchaseOrderReceiveView.as_view(),
        name='purchase_order_receive',
    ),
    path(
        'purchase-orders/<int:pk>/delete/',
        PurchaseOrderDeleteView.as_view(),
        name='purchase_order_delete',
    ),
    path('sales-orders/', SalesOrderListView.as_view(), name='sales_order_list'),
    path(
        'sales-orders/create/',
        SalesOrderCreateView.as_view(),
        name='sales_order_create',
    ),
    path(
        'sales-orders/<int:pk>/',
        SalesOrderDetailView.as_view(),
        name='sales_order_detail',
    ),
    path(
        'sales-orders/<int:pk>/update/',
        SalesOrderUpdateView.as_view(),
        name='sales_order_update',
    ),
    path(
        'sales-orders/<int:pk>/dispatch/',
        SalesOrderDispatchView.as_view(),
        name='sales_order_dispatch',
    ),
    path(
        'sales-orders/<int:pk>/delete/',
        SalesOrderDeleteView.as_view(),
        name='sales_order_delete',
    ),
    path(
        'stock-movements/',
        StockMovementListView.as_view(),
        name='stock_movement_list',
    ),
    path(
        'stock-movements/create/',
        StockMovementCreateView.as_view(),
        name='stock_movement_create',
    ),
    path(
        'stock-movements/<int:pk>/',
        StockMovementDetailView.as_view(),
        name='stock_movement_detail',
    ),
]

from django.urls import include, path

urlpatterns = [
    path('', include('core.urls.auth')),
    path('dashboard/', include('core.urls.dashboard')),
    path('categories/', include('core.urls.categories')),
    path('products/', include('core.urls.products')),
    path('suppliers/', include('core.urls.suppliers')),
    path('customers/', include('core.urls.customers')),
    path('purchase-orders/', include('core.urls.purchases')),
    path('sales-orders/', include('core.urls.sales')),
    path('stock-movements/', include('core.urls.stock')),
]

from core.forms.auth import LoginForm
from core.forms.catalog import CategoryForm, ProductForm
from core.forms.partners import CustomerForm, SupplierForm
from core.forms.purchases import PurchaseOrderForm, PurchaseOrderItemFormSet
from core.forms.sales import SalesOrderForm, SalesOrderItemFormSet
from core.forms.stock import StockMovementForm

__all__ = [
    'CategoryForm',
    'CustomerForm',
    'LoginForm',
    'ProductForm',
    'PurchaseOrderForm',
    'PurchaseOrderItemFormSet',
    'SalesOrderForm',
    'SalesOrderItemFormSet',
    'StockMovementForm',
    'SupplierForm',
]

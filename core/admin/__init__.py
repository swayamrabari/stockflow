from core.admin.assistant import ChatAdmin
from core.admin.catalog import CategoryAdmin, ProductAdmin
from core.admin.partners import CustomerAdmin, SupplierAdmin
from core.admin.purchases import PurchaseOrderAdmin, PurchaseOrderItemAdmin
from core.admin.sales import SalesOrderAdmin, SalesOrderItemAdmin
from core.admin.stock import StockMovementAdmin
from core.admin.users import UserAdmin

__all__ = [
    'CategoryAdmin',
    'ChatAdmin',
    'CustomerAdmin',
    'ProductAdmin',
    'PurchaseOrderAdmin',
    'PurchaseOrderItemAdmin',
    'SalesOrderAdmin',
    'SalesOrderItemAdmin',
    'StockMovementAdmin',
    'SupplierAdmin',
    'UserAdmin',
]

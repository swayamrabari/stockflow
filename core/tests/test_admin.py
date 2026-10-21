from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Category,
    Customer,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    SalesOrderItem,
    StockMovement,
    Supplier,
)
from core.tests.helpers import PASSWORD, User

MODELS = (
    Category,
    Product,
    Supplier,
    Customer,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    SalesOrderItem,
    StockMovement,
    User,
)


class AdminRegistrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='root',
            email='root@example.com',
            password=PASSWORD,
        )
        self.client.force_login(self.admin)

    def test_every_model_is_registered(self):
        for model in MODELS:
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))

    def test_every_admin_changelist_loads(self):
        for model in MODELS:
            with self.subTest(model=model.__name__):
                response = self.client.get(
                    reverse(f'admin:core_{model._meta.model_name}_changelist')
                )
                self.assertEqual(response.status_code, 200)

from django import forms
from django.forms import inlineformset_factory

from core.forms.orders import BaseOrderItemFormSet, OrderItemQuantityMixin
from core.models import Product, SalesOrder, SalesOrderItem


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ('customer', 'is_direct')
        widgets = {  # noqa: RUF012
            'is_direct': forms.CheckboxInput(
                attrs={
                    'class': 'size-5 shrink-0 border border-black accent-black',
                }
            ),
        }


class ProductWithStockChoiceField(forms.ModelChoiceField):
    """Show the current stock level alongside each product in a dropdown."""

    def label_from_instance(self, product):
        return f'{product.sku} - {product.name} ({product.quantity_in_stock} in stock)'


class SalesOrderItemForm(OrderItemQuantityMixin, forms.ModelForm):
    product = ProductWithStockChoiceField(queryset=Product.objects.all())

    class Meta:
        model = SalesOrderItem
        fields = ('product', 'quantity')


SalesOrderItemFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderItem,
    form=SalesOrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)

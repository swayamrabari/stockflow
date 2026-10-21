from django import forms
from django.forms import inlineformset_factory

from core.forms.orders import BaseOrderItemFormSet, OrderItemQuantityMixin
from core.models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ('supplier', 'is_direct')
        widgets = {  # noqa: RUF012
            'is_direct': forms.CheckboxInput(
                attrs={
                    'class': 'size-5 shrink-0 border border-black accent-black',
                }
            ),
        }


class PurchaseOrderItemForm(OrderItemQuantityMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ('product', 'quantity')


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)

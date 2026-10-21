from django import forms

from core.models import Customer, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            'name',
            'email',
            'phone',
            'address',
        )


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            'name',
            'email',
            'phone',
            'address',
        )

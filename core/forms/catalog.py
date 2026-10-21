from django import forms

from core.models import Category, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description')


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            'sku',
            'name',
            'description',
            'category',
            'reorder_level',
        )

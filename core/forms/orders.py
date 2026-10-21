from django import forms


class OrderItemQuantityMixin:
    def clean_quantity(self):
        """Mirror the DB check constraint so users get a field error."""
        quantity = self.cleaned_data.get('quantity')

        if quantity is not None and quantity <= 0:
            raise forms.ValidationError('Quantity must be greater than zero.')

        return quantity


class BaseOrderItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        """Reject the same product appearing more than once in one order."""
        super().clean()

        if any(self.errors):
            return

        seen = set()

        for form in self.forms:
            if not form.cleaned_data or self._should_delete_form(form):
                continue

            product = form.cleaned_data.get('product')

            if product is None:
                continue

            if product.pk in seen:
                form.add_error('product', 'This product is already in the order.')

            seen.add(product.pk)

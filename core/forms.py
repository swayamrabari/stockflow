from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.forms import inlineformset_factory

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


class RegistrationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide the default help/instruction text (password rules, etc.)
        for field in self.fields.values():
            field.help_text = ''


class LoginForm(AuthenticationForm):
    pass


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


class OrderItemQuantityMixin:
    def clean_quantity(self):
        """Mirror the DB check constraint so users get a field error."""
        quantity = self.cleaned_data.get('quantity')

        if quantity is not None and quantity <= 0:
            raise forms.ValidationError('Quantity must be greater than zero.')

        return quantity


class PurchaseOrderItemForm(OrderItemQuantityMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ('product', 'quantity')


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


class BaseOrderItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        """Reject the same product appearing more than once in one order."""
        super().clean()

        if any(self.errors):
            return

        seen = set()

        for form in self.forms:
            # A row marked for deletion is skipped entirely, so it can't
            # trip the duplicate check on its way out.
            if not form.cleaned_data or self._should_delete_form(form):
                continue

            product = form.cleaned_data.get('product')

            if product is None:
                continue

            if product.pk in seen:
                form.add_error('product', 'This product is already in the order.')

            seen.add(product.pk)


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


class StockMovementForm(forms.Form):
    """Record a manual stock movement.

    The user always types a positive quantity; the form works out the
    signed change from the movement type (and, for adjustments, the
    direction toggle).
    """

    INCREASE = 'increase'
    DECREASE = 'decrease'
    DIRECTION_CHOICES = (
        (INCREASE, 'Increase'),
        (DECREASE, 'Decrease'),
    )

    product = forms.ModelChoiceField(queryset=Product.objects.all())
    movement_type = forms.ChoiceField(choices=StockMovement.MovementType.choices)
    quantity = forms.IntegerField(
        min_value=1,
        label='Quantity',
        help_text='Always a positive number.',
    )
    direction = forms.ChoiceField(
        choices=DIRECTION_CHOICES,
        required=False,
        widget=forms.RadioSelect,
        label='Direction',
        help_text='Only used for adjustments.',
    )
    reference_note = forms.CharField(
        required=False,
        widget=forms.Textarea,
        label='Reference note',
    )

    def clean(self):
        cleaned = super().clean()

        product = cleaned.get('product')
        movement_type = cleaned.get('movement_type')
        quantity = cleaned.get('quantity')
        direction = cleaned.get('direction')

        if movement_type == StockMovement.MovementType.ADJUSTMENT and not direction:
            self.add_error('direction', 'Choose whether stock goes up or down.')
            return cleaned

        if not (product and movement_type and quantity):
            return cleaned

        # Work out the signed change the same way save() will.
        self.change = quantity

        decrease = movement_type == StockMovement.MovementType.OUTGOING or (
            movement_type == StockMovement.MovementType.ADJUSTMENT
            and direction == self.DECREASE
        )

        if decrease:
            self.change = -quantity

        if product.quantity_in_stock + self.change < 0:
            self.add_error(
                'quantity',
                f'Not enough stock: only {product.quantity_in_stock} available.',
            )

        return cleaned

    def save(self, user):
        return StockMovement.record(
            product=self.cleaned_data['product'],
            quantity=self.change,
            movement_type=self.cleaned_data['movement_type'],
            user=user,
            note=self.cleaned_data['reference_note'],
        )




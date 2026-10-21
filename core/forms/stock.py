from django import forms

from core.models import Product, StockMovement


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

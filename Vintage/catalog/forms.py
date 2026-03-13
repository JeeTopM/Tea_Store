from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Store, ProductCategory, Product, ProductBatch, Stock, StockMovement, Gift


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название магазина'}),
            'address': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'г. Москва, ул. Примерная, д. 1'}),
        }


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-control'}),
        }


class ProductBatchForm(forms.ModelForm):
    class Meta:
        model = ProductBatch
        fields = [
            'product', 'barcode', 'production_date', 'expiration_date',
            'price', 'is_available',
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select select2'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '4601234567890'}),
            'production_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = (
            Product.objects.select_related('category').order_by('category__name', 'name')
        )
        self.fields['product'].label_from_instance = lambda obj: f"{obj.category.name} — {obj.name}"

    def clean(self):
        cleaned_data = super().clean()
        production_date = cleaned_data.get('production_date')
        expiration_date = cleaned_data.get('expiration_date')

        if production_date and expiration_date and expiration_date <= production_date:
            self.add_error('expiration_date', 'Срок годности должен быть позже даты изготовления')
        elif production_date and production_date > timezone.now().date():
            self.add_error('production_date', 'Дата изготовления не может быть в будущем')

        return cleaned_data


class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ['store', 'quantity']
        widgets = {
            'store': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class StockMovementForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label='Количество', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    comment = forms.CharField(required=False, label='Комментарий', widget=forms.TextInput(attrs={'class': 'form-control'}))


class GiftForm(forms.ModelForm):
    class Meta:
        model = Gift
        fields = ['store', 'note']
        widgets = {
            'store': forms.Select(attrs={'class': 'form-control'}),
            'note': forms.TextInput(attrs={'class': 'form-control'}),
        }


class GiftAddStockItemForm(forms.Form):
    stock = forms.ModelChoiceField(
        queryset=Stock.objects.none(),
        label='Остаток (партия в магазине)',
        widget=forms.Select(attrs={'class': 'form-control select2'}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        label='Количество',
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    note = forms.CharField(
        required=False,
        label='Комментарий',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)

        qs = (
            Stock.objects
            .select_related('store', 'batch__product__category')
            .filter(quantity__gt=0)
            .order_by('batch__product__category__name', 'batch__product__name', 'batch__expiration_date')
        )
        if store is not None:
            qs = qs.filter(store=store)

        self.fields['stock'].queryset = qs

        def _label(obj: Stock):
            p = obj.batch.product
            unit = p.get_unit_display() if hasattr(p, 'get_unit_display') else ''
            cat = getattr(p.category, 'name', '')
            return f"{cat} — {p.name} | до {obj.batch.expiration_date} | остаток {obj.quantity} {unit}"

        self.fields['stock'].label_from_instance = _label


class GiftCreateForStoreForm(forms.ModelForm):
    class Meta:
        model = Gift
        fields = ['note']
        widgets = {
            'note': forms.TextInput(attrs={'class': 'form-control'}),
        }


class GiftAddExtraItemForm(forms.Form):
    extra_name = forms.CharField(label='Название', widget=forms.TextInput(attrs={'class': 'form-control'}))
    quantity = forms.IntegerField(min_value=1, label='Количество', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    unit_price = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        max_digits=10,
        label='Цена за единицу',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
    )
    note = forms.CharField(required=False, label='Комментарий', widget=forms.TextInput(attrs={'class': 'form-control'}))


class GiftSellForm(forms.Form):
    sale_price = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        max_digits=10,
        label='Цена продажи',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
    )

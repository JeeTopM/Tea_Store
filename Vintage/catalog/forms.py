from django import forms
from django.utils import timezone

from .models import Store, ProductCategory, Product, ProductBatch


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название магазина'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'г. Москва, ул. Примерная, д. 1'}),
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
        fields = ['name', 'description', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }


class ProductBatchForm(forms.ModelForm):
    class Meta:
        model = ProductBatch
        fields = ['product', 'store', 'barcode', 'production_date', 'expiration_date', 'quantity', 'price', 'is_available']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control select2'}),
            'store': forms.Select(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '4601234567890'}),
            'production_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
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